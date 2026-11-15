import logging
from src.graph_client import GraphLabDriver
from src.opensearch_client import OpenSearchVectorStore
from src.pgvector_client import PgVectorStore
from src.memory_client import SessionMemoryStore
from src.schema_init import initialize_database
from src.ingestion import (
    ingest_ontology_class,
    ingest_governed_metric,
    dual_ingest_document_chunk,
)
from src.retriever import SemanticGraphRetriever

logging.basicConfig(level=logging.INFO)


def seed():
    """Initialize + seed every store (Neo4j, OpenSearch, Aurora pgvector,
    DynamoDB). Write-only and defect-independent, so it succeeds on the DIY
    (broken) start state. Does NOT run the retrieval self-test — see demo()."""
    lab = GraphLabDriver()
    os_store = OpenSearchVectorStore()
    os_store.wait_until_ready()
    pg_store = PgVectorStore()
    try:
        print("\n--- 1. Initializing Neo4j schema + OpenSearch k-NN + pgvector ---")
        initialize_database(lab, os_store)
        pg_store.initialize()
        pg_store.seed_quarterly_capital()

        print("\n--- 1b. Seeding demo conversational session (DynamoDB) ---")
        memory = SessionMemoryStore()
        memory.seed_turn("s-demo", 1, "user", "I need to review the Nexus Tower commercial property policy.")
        memory.seed_turn("s-demo", 2, "assistant", "Sure — Nexus Tower is a commercial property policy. What would you like to check?")
        memory.seed_turn("s-demo", 3, "user", "Which governed metric applies to it?")
        print("Demo session 's-demo' seeded with 3 turns.")

        print("\n--- 2. Ingesting ontology classes ---")
        ingest_ontology_class(
            lab,
            uri="urn:coa:ontology:FinancialAsset",
            name="FinancialAsset",
            description="Base classification for capital, equity, and asset holdings.",
        )
        ingest_ontology_class(
            lab,
            uri="urn:coa:ontology:CommercialPropertyPolicy",
            name="CommercialPropertyPolicy",
            description="Insurance policies covering commercial physical assets and liabilities.",
            parent_uri="urn:coa:ontology:FinancialAsset",
        )

        print("\n--- 3. Ingesting governed metric ---")
        ingest_governed_metric(
            lab,
            name="solvency_ii_ratio",
            description="Solvency II Capital Requirement Ratio for commercial lines.",
            calculation_template="SELECT eligible_own_funds / scr AS ratio FROM quarterly_capital WHERE line_of_business = :lob",
            target_class_uris=["urn:coa:ontology:CommercialPropertyPolicy"],
            properties_used=["eligible_own_funds", "scr", "line_of_business"],
        )

        print("\n--- 4. Dual-ingesting document chunk (OpenSearch vector + Neo4j graph) ---")
        dual_ingest_document_chunk(
            lab,
            os_store,
            chunk_id="doc_chunk_101",
            text="Underwriting update for Nexus Tower: Commercial property policy underwritten with full catastrophic risk exclusion.",
            source_uri="doc://underwriting/nexus-tower-2026",
            extracted_entities=[
                {
                    "id": "ent_nexus_tower",
                    "name": "Nexus Tower",
                    "type": "CommercialProperty",
                    "confidence": 0.98,
                }
            ],
            pg_store=pg_store,
        )

        # aoss is eventually-consistent: the just-indexed chunk is not
        # immediately searchable (~60-70s). Block here so any later retrieval
        # (demo/self-test, or the learner's first query) sees it.
        print("\n--- 4b. Waiting for OpenSearch (Serverless) consistency ---")
        os_store.wait_until_searchable(expected_count=1)

        print("\n--- Seed complete (stores initialized + demo session seeded) ---")
    finally:
        lab.close()
        pg_store.close()


def demo():
    """Answer-key retrieval self-test (Test A + Test B) """
    lab = GraphLabDriver()
    os_store = OpenSearchVectorStore()
    os_store.wait_until_ready()
    try:
        print("\n--- Retrieval tests (answer-key demo) ---")
        retriever = SemanticGraphRetriever(lab, os_store)

        print("\n[Test A: Governed Metric Resolution]")
        metrics = retriever.resolve_governed_metric("Calculate Solvency 2 ratio for commercial policies")
        print("Metric Result:", metrics)

        print("\n[Test B: OpenSearch + Neo4j Graph Traversal]")
        traversal_results = retriever.hybrid_rag_traversal("What are the exclusions for Nexus Tower commercial property?")
        for res in traversal_results:
            print(f"\nChunk ID: {res['chunk_id']} (Score: {res['score']:.4f})")
            print(f"Chunk Text: {res['chunk_text']}")
            print(f"Source: {res['source']}")
            print(f"Grounded Entities: {res['grounded_entities']}")

        print("\n--- E2E complete ---")
    finally:
        lab.close()


def run_lab():
    """Answer-key full run: seed the stores, then run the retrieval self-test."""
    seed()
    demo()


if __name__ == "__main__":
    import sys

    # Deploy-time seeding calls `--seed-only`: it initializes + seeds every store
    # (defect-independent) and does NOT run the retrieval self-test, so it
    # succeeds on the DIY (broken) box. A plain run is the full answer-key demo.
    if "--seed-only" in sys.argv:
        seed()
    else:
        run_lab()
