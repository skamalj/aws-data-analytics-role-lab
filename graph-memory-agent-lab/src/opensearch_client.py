import time
import logging
from opensearchpy import OpenSearch
from src.config import (
    OPENSEARCH_HOST,
    OPENSEARCH_PORT,
    OPENSEARCH_USE_SIGV4,
    OPENSEARCH_SERVICE,
    OPENSEARCH_ENGINE,
    EMBEDDING_DIMENSIONS,
    AWS_REGION,
)

logger = logging.getLogger(__name__)
INDEX_NAME = "coa_chunks_knn"


class OpenSearchVectorStore:
    """Vector store A — document chunk vectors + BM25 text."""

    def __init__(self, host: str = OPENSEARCH_HOST, port: int = OPENSEARCH_PORT):
        # aoss collection endpoints arrive as https://<id>.<region>.aoss...;
        # strip any scheme so opensearch-py gets a bare host.
        host = host.replace("https://", "").replace("http://", "").rstrip("/")
        use_sigv4 = OPENSEARCH_USE_SIGV4 or int(port) == 443
        self.serverless = OPENSEARCH_SERVICE == "aoss"
        if use_sigv4:
            # Managed OpenSearch (es) or Serverless (aoss): HTTPS + SigV4.
            import boto3
            from opensearchpy import AWSV4SignerAuth, RequestsHttpConnection

            credentials = boto3.Session().get_credentials()
            auth = AWSV4SignerAuth(credentials, AWS_REGION, OPENSEARCH_SERVICE)
            self.client = OpenSearch(
                hosts=[{"host": host, "port": int(port)}],
                http_auth=auth,
                use_ssl=True,
                verify_certs=True,
                connection_class=RequestsHttpConnection,
                pool_maxsize=20,
                timeout=60,  # aoss Serverless can be slow on cold-start / first write
            )
        else:
            # Local/dev OpenSearch with the security plugin disabled.
            self.client = OpenSearch(
                hosts=[{"host": host, "port": int(port)}],
                use_ssl=False,
                verify_certs=False,
            )

    def wait_until_ready(self, retries: int = 20, delay: float = 3.0) -> None:
        """Confirm the data plane authorizes us. Uses a SCOPED indices.exists()
        (aoss data-access policies grant on index/collection resources, not on
        the '*' root a HEAD / would hit). A 403 here means an access-policy/IAM
        problem (fail fast); connection errors are retried."""
        from opensearchpy.exceptions import AuthorizationException, AuthenticationException

        last = None
        for attempt in range(1, retries + 1):
            try:
                self.client.indices.exists(index=INDEX_NAME)
                logger.info("Connected to OpenSearch (%s) at %s", OPENSEARCH_SERVICE, OPENSEARCH_HOST)
                return
            except (AuthorizationException, AuthenticationException) as exc:
                raise RuntimeError(
                    f"OpenSearch auth error ({getattr(exc, 'status_code', '403')}): access-policy/IAM "
                    "problem, not a readiness timeout. Verify the aoss data-access policy names this "
                    "role and aoss:APIAccessAll is granted."
                ) from exc
            except Exception as exc:  # noqa: BLE001
                last = exc
                logger.info("OpenSearch not ready (attempt %d/%d): %s", attempt, retries, exc)
            time.sleep(delay)
        raise RuntimeError(f"OpenSearch did not become reachable: {last}")

    def wait_until_searchable(self, expected_count: int, timeout: float = 180.0, interval: float = 3.0) -> int:
        """Block until >= expected_count docs are searchable."""
        waited = 0.0
        while waited < timeout:
            time.sleep(interval)
            waited += interval
            try:
                n = self.client.search(
                    index=INDEX_NAME, body={"size": 0, "query": {"match_all": {}}}
                )["hits"]["total"]["value"]
            except Exception:  # noqa: BLE001
                n = 0
            if n >= expected_count:
                logger.info("OpenSearch: %d docs searchable after ~%.0fs", n, waited)
                return int(waited)
        logger.warning("OpenSearch: consistency timeout after %.0fs (< %d docs)", waited, expected_count)
        return -1

    def initialize_index(self):
        """Create the k-NN index (HNSW, cosine, faiss) with a BM25 text field."""
        if not self.client.indices.exists(index=INDEX_NAME):
            index_body = {
                "settings": {"index": {"knn": True}},
                "mappings": {
                    "properties": {
                        "chunk_id": {"type": "keyword"},
                        "text": {"type": "text"},
                        "source_uri": {"type": "keyword"},
                        "entity_ids": {"type": "keyword"},
                        "embedding": {
                            "type": "knn_vector",
                            "dimension": EMBEDDING_DIMENSIONS,
                            "method": {
                                "name": "hnsw",
                                "space_type": "cosinesimil",
                                # aoss supports faiss/nmslib, NOT lucene.
                                "engine": OPENSEARCH_ENGINE,
                                "parameters": {"ef_construction": 128, "m": 16},
                            },
                        },
                    }
                },
            }
            self.client.indices.create(index=INDEX_NAME, body=index_body)
            logger.info("OpenSearch index '%s' initialized (engine=%s).", INDEX_NAME, OPENSEARCH_ENGINE)

    def index_chunk(self, chunk_id, text, source_uri, entity_ids, embedding):
        doc = {
            "chunk_id": chunk_id,
            "text": text,
            "source_uri": source_uri,
            "entity_ids": entity_ids,
            "embedding": embedding,
        }
        # aoss does NOT support refresh=True; visibility is eventually consistent
        # (callers use wait_until_searchable before querying). aoss also ignores
        # a client-supplied _id, so we don't pass id=.
        if self.serverless:
            self.client.index(index=INDEX_NAME, body=doc)
        else:
            self.client.index(index=INDEX_NAME, id=chunk_id, body=doc, refresh=True)

    def _knn(self, query_vector, k):
        body = {"size": k, "query": {"knn": {"embedding": {"vector": query_vector, "k": k}}}}
        hits = self.client.search(index=INDEX_NAME, body=body)["hits"]["hits"]
        return [self._to_doc(h) for h in hits]

    def _bm25(self, query_text, k):
        body = {"size": k, "query": {"match": {"text": query_text}}}
        hits = self.client.search(index=INDEX_NAME, body=body)["hits"]["hits"]
        return [self._to_doc(h) for h in hits]

    @staticmethod
    def _to_doc(hit):
        s = hit["_source"]
        return {
            "chunk_id": s["chunk_id"],
            "text": s["text"],
            "source_uri": s["source_uri"],
            "entity_ids": s.get("entity_ids", []),
        }

    def hybrid_vector_search(self, query_text, query_vector, top_k: int = 3, rrf_k: int = 60):
        """Hybrid search over BM25 (keyword) and kNN (vector), returning top_k docs."""
        # TODO(DIY-3): this hybrid query returns hits without a usable fused `score`.
        # Repair the method so BM25 and kNN results are combined into a single
        # ranked list where every returned hit carries a numeric `score`.
        body = {"size": top_k, "query": {"bool": {"should": [
            {"match": {"text": query_text}},
            {"knn": {"embedding": {"vector": query_vector, "k": top_k}}},
        ]}}}
        hits = self.client.search(index=INDEX_NAME, body=body)["hits"]["hits"]
        return [self._to_doc(h) for h in hits]
