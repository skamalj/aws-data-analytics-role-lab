# Mission D6: pgvector finds nothing, then finds it slowly

**Exam objective:** *Configure pgvector for document retrieval*
**Skills:** pgvector column types and dimensions, embedding-model dimensions on both the write and query side, HNSW operator classes vs distance operators, read-only grants for retrieval, checking index use with `EXPLAIN`
**Time:** 40 minutes  |  **Needs:** `./scripts/deploy.sh base`, then `./scripts/deploy.sh D6`, then `python3 missions/D6-pgvector-document-retrieval/ingest.py`

## Situation

The architects decided Trail Desk should search Riverbend's documents **itself**: no Knowledge
Base, just pgvector in the shared Aurora cluster, so they control chunking, scoring and filtering.

- [`ingest.py`](ingest.py) chunks `docs/*.md`, embeds each chunk with **Titan Text Embeddings V2** and upserts it into `knowledge.doc_chunks`.
- [`db/schema.sql`](db/schema.sql) defines the table, its HNSW index and the agent's grants (applied by `setup.py` on every deploy).
- The agent's `search_docs` tool ([`lambdas/doc_search.py`](lambdas/doc_search.py)) embeds the question the same way and ranks chunks by **cosine distance** (`<=>`), logging in as `trail_desk_app`.

```
docs/*.md ─ ingest.py ─ Titan V2 ─► knowledge.doc_chunks (vector(1024), HNSW)
Trail Desk ─ search_docs ─► Lambda ─ Titan V2 (query) ─► SELECT … ORDER BY embedding <=> :q LIMIT 4   (as trail_desk_app)
```

## Symptoms

```bash
python3 missions/D6-pgvector-document-retrieval/ingest.py
python3 missions/D6-pgvector-document-retrieval/scenarios/check.py
python3 common/chat.py D6 "How do I restore the water repellency of my rain jacket?"
```

## Objectives

1. All 5 documents are ingested with embeddings that the column and the query agree on.
2. `search_docs` returns the right passages for the agent, as `trail_desk_app`, read-only.
3. The similarity query can be served by the HNSW index, not only by a full table scan.
4. Keep cosine similarity (Titan vectors are normalised) and keep the 1024-dimension column.

## Done when

```
PASS  documents are ingested (5 docs, 1024-d vectors)
PASS  trail_desk_app can read knowledge.doc_chunks
PASS  trail_desk_app cannot modify knowledge.doc_chunks
PASS  the cosine search (<=>) can use the HNSW index
PASS  search_docs returns the rain-jacket care guide first
```

## Investigation toolkit

```bash
python3 common/dbsql.py --sql "SELECT doc, count(*), min(vector_dims(embedding)) FROM knowledge.doc_chunks GROUP BY doc"
python3 common/dbsql.py --sql "SELECT indexdef FROM pg_indexes WHERE schemaname = 'knowledge'"
python3 common/dbsql.py --sql "SELECT grantee, privilege_type FROM information_schema.role_table_grants WHERE table_schema = 'knowledge'"
python3 common/dbsql.py --as app --sql "SELECT count(*) FROM knowledge.doc_chunks"
aws logs tail /aws/lambda/riverbend-d6-doc-search --since 10m
```

`EXPLAIN` tip: the table is small, so PostgreSQL may scan it anyway. To see whether an index **can** be used, run the query
in a transaction after `SET LOCAL enable_seqscan = off`. `scenarios/check.py` does exactly that.

## Hint ladder

<details><summary>Hint 1: ingestion fails</summary>Compare the length of the vectors the job produces with the column type. Titan V2 supports 256, 512 and 1024 dimensions. Which value does everything else in the system assume?</details>
<details><summary>Hint 2: permission denied</summary>Schema <code>USAGE</code> lets you see objects in the schema. It doesn't let you read them.</details>
<details><summary>Hint 3: the index is never used</summary>pgvector has one operator class per distance: <code>vector_l2_ops</code> (<code>&lt;-&gt;</code>), <code>vector_ip_ops</code> (<code>&lt;#&gt;</code>), <code>vector_cosine_ops</code> (<code>&lt;=&gt;</code>). An index only serves queries that use its operator.</details>

## Debrief questions

1. If you switched to 512-dimension embeddings, which three places must change together?
2. For normalised vectors, cosine, inner product and L2 give the same ranking. Why does the operator class still matter?
3. What do `hnsw.ef_search`, `m` and `ef_construction` trade off? (Mission D10 goes deeper.)
4. Why does the ingestion job use a different database identity from the agent?
