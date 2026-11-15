"""
Offline self-checks for the five goals: no AWS account, Neo4j, OpenSearch or PostgreSQL needed.
DynamoDB is simulated with moto; the other stores are replaced by small fakes.

    pytest tests -q              # everything
    pytest tests -q -k goal4     # one goal

They fail on the lab's starting code and pass once a goal is fixed. They check your code only:
the graded evidence still has to be produced against the real stores (see the notebooks).
"""
import asyncio
import importlib
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
for k, v in {"AWS_ACCESS_KEY_ID": "testing", "AWS_SECRET_ACCESS_KEY": "testing", "AWS_SESSION_TOKEN": "testing",
             "AWS_DEFAULT_REGION": "us-east-1"}.items():
    os.environ[k] = v


# ----------------------------------------------------------------- fakes
class FakeSession:
    def __init__(self, calls):
        self.calls = calls

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute_read(self, fn, query):
        self.calls.append(query)
        return []

    def run(self, *a, **k):
        self.calls.append(a[0] if a else "")
        return []


class FakeDriver:
    def __init__(self):
        self.calls = []

    def session(self, **kw):
        return FakeSession(self.calls)

    def close(self):
        pass


class FakeLab:
    def __init__(self, *a, **k):
        self.driver = FakeDriver()

    def get_embedding(self, text):
        return [0.0] * 8

    def close(self):
        pass


class FakeStore:
    def __init__(self, *a, **k):
        self.waited_for = None

    def wait_until_ready(self, *a, **k):
        pass

    def wait_until_searchable(self, expected_count, *a, **k):
        self.waited_for = expected_count
        return 0

    def initialize(self):
        pass

    def seed_quarterly_capital(self):
        pass

    def close(self):
        pass


class FakeMemory:
    def __init__(self, *a, **k):
        self.turns = {}

    def seed_turn(self, session_id, turn_id, role, content):
        self.turns.setdefault(session_id, {})[turn_id] = (role, content)

    def append_turn(self, session_id, role, content):
        nxt = max(self.turns.get(session_id, {0: None})) + 1
        self.turns.setdefault(session_id, {})[nxt] = (role, content)
        return nxt

    def get_session(self, session_id):
        return [{"turn_id": t, "role": r, "content": c} for t, (r, c) in sorted(self.turns.get(session_id, {}).items())]


@pytest.fixture
def mcp_server(monkeypatch):
    """Import src.mcp_server with every store replaced by a fake (it connects at import time)."""
    import src.graph_client
    import src.memory_client
    import src.opensearch_client
    import src.pgvector_client
    monkeypatch.setattr(src.graph_client, "GraphLabDriver", FakeLab)
    monkeypatch.setattr(src.opensearch_client, "OpenSearchVectorStore", FakeStore)
    monkeypatch.setattr(src.memory_client, "SessionMemoryStore", FakeMemory)
    monkeypatch.setattr(src.pgvector_client, "PgVectorStore", FakeStore)
    for mod in ("src.retriever", "src.mcp_server"):
        sys.modules.pop(mod, None)
    return importlib.import_module("src.mcp_server")


# ----------------------------------------------------------------- goal 1
def test_goal1_get_session_returns_oldest_first():
    from moto import mock_aws
    import boto3
    with mock_aws():
        boto3.client("dynamodb", region_name="us-east-1").create_table(
            TableName="claims-sessions", BillingMode="PAY_PER_REQUEST",
            KeySchema=[{"AttributeName": "session_id", "KeyType": "HASH"}, {"AttributeName": "turn_id", "KeyType": "RANGE"}],
            AttributeDefinitions=[{"AttributeName": "session_id", "AttributeType": "S"}, {"AttributeName": "turn_id", "AttributeType": "N"}])
        from src.memory_client import SessionMemoryStore
        m = SessionMemoryStore(table_name="claims-sessions", region="us-east-1")
        for i in (1, 2, 3):
            m.seed_turn("s-demo", i, "user", f"turn {i}")
        assert [t["turn_id"] for t in m.get_session("s-demo")] == [1, 2, 3], "get_session must return turns oldest first"
        assert m.append_turn("s-demo", "assistant", "turn 4") == 4, "append_turn must assign the next id (and not overwrite turn 2)"
        assert [t["content"] for t in m.get_session("s-demo")] == ["turn 1", "turn 2", "turn 3", "turn 4"]
        assert m.get_session("s-unknown") == []


def test_goal1_memory_tools_registered(mcp_server):
    names = {t.name for t in asyncio.run(mcp_server.mcp.list_tools())}
    assert {"append_turn", "get_session"} <= names, f"registered tools: {sorted(names)}"


def test_goal1_memory_tools_behave(mcp_server):
    import json
    assert hasattr(mcp_server, "append_turn") and hasattr(mcp_server, "get_session"), "define append_turn and get_session"
    r1 = json.loads(mcp_server.append_turn("s-x", "user", "hello"))
    r2 = json.loads(mcp_server.append_turn("s-x", "assistant", "hi"))
    assert r1 == {"session_id": "s-x", "turn_id": 1} and r2["turn_id"] == 2
    turns = json.loads(mcp_server.get_session("s-x"))
    assert [t["turn_id"] for t in turns] == [1, 2] and turns[0]["content"] == "hello"


# ----------------------------------------------------------------- goal 3
def test_goal3_seed_builds_both_lines(monkeypatch):
    import src.main as main
    calls = []
    monkeypatch.setattr(main, "GraphLabDriver", FakeLab)
    os_store = FakeStore()
    monkeypatch.setattr(main, "OpenSearchVectorStore", lambda *a, **k: os_store)
    monkeypatch.setattr(main, "PgVectorStore", FakeStore)
    monkeypatch.setattr(main, "SessionMemoryStore", FakeMemory)
    monkeypatch.setattr(main, "initialize_database", lambda *a, **k: None)
    monkeypatch.setattr(main, "ingest_ontology_class", lambda lab, **k: calls.append(("class", k)))
    monkeypatch.setattr(main, "ingest_governed_metric", lambda lab, **k: calls.append(("metric", k)))
    monkeypatch.setattr(main, "dual_ingest_document_chunk", lambda lab, store, **k: calls.append(("chunk", k)))
    main.seed()

    classes = {k["uri"]: (i, k) for i, (kind, k) in enumerate(calls) if kind == "class"}
    metrics = {k["name"]: (i, k) for i, (kind, k) in enumerate(calls) if kind == "metric"}
    chunks = {k["chunk_id"]: k for kind, k in calls if kind == "chunk"}
    marine = "urn:coa:ontology:MarineCargoPolicy"
    assert marine in classes, "ingest the MarineCargoPolicy class"
    assert classes[marine][1].get("parent_uri") == "urn:coa:ontology:FinancialAsset"
    assert "cargo_loss_ratio" in metrics, "ingest the cargo_loss_ratio governed metric"
    assert metrics["cargo_loss_ratio"][1]["target_class_uris"] == [marine]
    assert classes[marine][0] < metrics["cargo_loss_ratio"][0], "ingest the class before the metric that is computed over it"
    nexus = chunks["doc_chunk_101"]["extracted_entities"][0]
    assert nexus.get("class_uri") == "urn:coa:ontology:CommercialPropertyPolicy", "Nexus Tower needs its class_uri"
    assert "doc_chunk_102" in chunks, "dual-ingest the Atlantic Freight chunk"
    af = chunks["doc_chunk_102"]
    ent = af["extracted_entities"][0]
    assert ent["id"] == "ent_atlantic_freight" and ent.get("class_uri") == marine
    assert af.get("pg_store") is not None, "pass pg_store so the chunk reaches pgvector too"
    assert os_store.waited_for == 2, "wait until both chunks are searchable"


# ----------------------------------------------------------------- goal 4
def _doc(cid):
    return {"chunk_id": cid, "text": f"text {cid}", "source_uri": f"doc://{cid}", "entity_ids": [f"ent_{cid}"]}


def test_goal4_rrf_fuses_and_scores():
    from src.opensearch_client import OpenSearchVectorStore
    s = object.__new__(OpenSearchVectorStore)                 # no client needed
    s._bm25 = lambda q, k: [_doc("A"), _doc("A"), _doc("B"), _doc("C")]   # duplicate A (aoss ignores ids on re-seed)
    s._knn = lambda v, k: [_doc("C"), _doc("A"), _doc("D")]
    hits = s.hybrid_vector_search("q", [0.0], top_k=3)
    assert len(hits) == 3, "return top_k hits"
    assert all(isinstance(h.get("score"), float) for h in hits), "every hit carries a numeric score"
    got = {h["chunk_id"]: round(h["score"], 6) for h in hits}
    assert got == {"A": round(1 / 61 + 1 / 62, 6), "C": round(1 / 63 + 1 / 61, 6), "B": round(1 / 62, 6)}, f"scores: {got}"
    assert [h["chunk_id"] for h in hits] == ["A", "C", "B"], "ranked by fused score, highest first"
    assert hits[0]["source_uri"] == "doc://A" and hits[0]["entity_ids"] == ["ent_A"], "keep the document fields"


# ----------------------------------------------------------------- goal 5
PROBES = [
    ("MATCH (c:OntologyClass) RETURN c.name", True),
    ("match (m:GovernedMetric)-[:COMPUTED_OVER]->(c) return m.name", True),
    ("OPTIONAL MATCH (e:Entity) RETURN count(e)", True),
    ("UNWIND [1, 2] AS x RETURN x", True),
    ("CALL dbms.components() YIELD name RETURN name", False),
    ("call\n  db.labels()", False),
    ("MATCH (n) RETURN apoc.version()", False),
    ("MATCH (n) DETACH DELETE n", False),
    ("MATCH (e:Entity) SET e.name = 'x' RETURN e", False),
    ("LOAD CSV FROM 'file:///x.csv' AS row RETURN row", False),
    ("MATCH (c) WITH c CALL { MATCH (x) RETURN count(x) AS n } RETURN n", False),
    ("SHOW USERS", False),
]


@pytest.mark.parametrize("query,admit", PROBES)
def test_goal5_guard(mcp_server, query, admit):
    resp = mcp_server.execute_read_cypher(query)
    reached_db = query in mcp_server.lab.driver.calls
    if admit:
        assert not resp.startswith("Rejected:") and reached_db, f"a genuine read must run: {resp}"
    else:
        assert resp.startswith("Rejected:"), f"must be rejected with 'Rejected:': {resp}"
        assert not reached_db, "a rejected query must never reach the database"
