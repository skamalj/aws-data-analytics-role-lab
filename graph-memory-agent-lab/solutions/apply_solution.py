"""
Apply the reference fix for one or more goals to src/ (and, for goal 2, to IAM).

    python solutions/apply_solution.py 1 3 4 5        # code goals
    python solutions/apply_solution.py 2 --yes        # deletes the inline policy vector-memory-leak

Each edit replaces an exact snippet of the original lab code and refuses if the snippet isn't found
(for example, because you already edited the file by hand). Undo code changes with `git checkout -- src/`.
After applying, you still have to run the goal's emit_evidence step and upload the result.
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def edit(path, old, new):
    p = os.path.join(ROOT, path)
    s = open(p).read()
    if new in s:
        print(f"  {path}: already applied")
        return
    if s.count(old) != 1:
        sys.exit(f"  {path}: expected snippet not found exactly once - has the file been edited? Restore it with git checkout.")
    open(p, "w").write(s.replace(old, new))
    print(f"  {path}: patched")


GOAL1_TOOLS = '''@mcp.tool()
def append_turn(session_id: str, role: str, content: str) -> str:
    """Append one conversational turn to a session; returns the new turn_id."""
    turn_id = memory.append_turn(session_id, role, content)
    return json.dumps({"session_id": session_id, "turn_id": turn_id})


@mcp.tool()
def get_session(session_id: str) -> str:
    """Return all turns for a session, oldest first."""
    return json.dumps(memory.get_session(session_id), indent=2)
'''


def goal1():
    print("Goal 1: memory tools and turn order")
    edit("src/memory_client.py", "ScanIndexForward=False,", "ScanIndexForward=True,")
    edit("src/mcp_server.py", "# TODO(DIY-1): register the Memory MCP tools here.\n", GOAL1_TOOLS)


def goal2(yes):
    print("Goal 2: IAM ownership boundary")
    from dotenv import load_dotenv
    import boto3
    load_dotenv(os.path.join(ROOT, ".env"))
    role = os.environ["MCP_VECTOR_ROLE_NAME"]
    iam = boto3.client("iam", region_name=os.getenv("AWS_REGION", "us-east-1"))
    names = iam.list_role_policies(RoleName=role)["PolicyNames"]
    if "vector-memory-leak" not in names:
        print(f"  {role}: vector-memory-leak already deleted ({names})")
        return
    if not yes:
        sys.exit(f"  would delete inline policy vector-memory-leak from {role}: re-run with --yes")
    iam.delete_role_policy(RoleName=role, PolicyName="vector-memory-leak")
    print(f"  {role}: deleted vector-memory-leak (kept {[n for n in names if n != 'vector-memory-leak']})")


GOAL3_NEXUS_OLD = '''                    "type": "CommercialProperty",
                    "confidence": 0.98,
                }'''
GOAL3_NEXUS_NEW = '''                    "type": "CommercialProperty",
                    "confidence": 0.98,
                    "class_uri": "urn:coa:ontology:CommercialPropertyPolicy",
                }'''
GOAL3_CLASS_OLD = '''            parent_uri="urn:coa:ontology:FinancialAsset",
        )

        print("\\n--- 3. Ingesting governed metric ---")'''
GOAL3_CLASS_NEW = '''            parent_uri="urn:coa:ontology:FinancialAsset",
        )
        ingest_ontology_class(
            lab,
            uri="urn:coa:ontology:MarineCargoPolicy",
            name="MarineCargoPolicy",
            description="Insurance policies covering goods in transit by sea and related cargo liabilities.",
            parent_uri="urn:coa:ontology:FinancialAsset",
        )

        print("\\n--- 3. Ingesting governed metric ---")'''
GOAL3_METRIC_OLD = '''            properties_used=["eligible_own_funds", "scr", "line_of_business"],
        )
'''
GOAL3_METRIC_NEW = '''            properties_used=["eligible_own_funds", "scr", "line_of_business"],
        )
        ingest_governed_metric(
            lab,
            name="cargo_loss_ratio",
            description="Loss ratio for marine cargo lines: incurred losses divided by earned premium.",
            calculation_template="SELECT incurred_losses / earned_premium AS ratio FROM cargo_experience WHERE line_of_business = :lob",
            target_class_uris=["urn:coa:ontology:MarineCargoPolicy"],
            properties_used=["incurred_losses", "earned_premium", "line_of_business"],
        )
'''
GOAL3_CHUNK_OLD = '''            pg_store=pg_store,
        )

        # aoss is eventually-consistent'''
GOAL3_CHUNK_NEW = '''            pg_store=pg_store,
        )
        dual_ingest_document_chunk(
            lab,
            os_store,
            chunk_id="doc_chunk_102",
            text="Underwriting update for Atlantic Freight: Marine cargo policy underwritten for transatlantic container shipments with piracy and war risk exclusions.",
            source_uri="doc://underwriting/atlantic-freight-2026",
            extracted_entities=[
                {
                    "id": "ent_atlantic_freight",
                    "name": "Atlantic Freight",
                    "type": "MarineCargo",
                    "confidence": 0.97,
                    "class_uri": "urn:coa:ontology:MarineCargoPolicy",
                }
            ],
            pg_store=pg_store,
        )

        # aoss is eventually-consistent'''


def goal3():
    print("Goal 3: knowledge graph ontology")
    edit("src/main.py", GOAL3_NEXUS_OLD, GOAL3_NEXUS_NEW)
    edit("src/main.py", GOAL3_CLASS_OLD, GOAL3_CLASS_NEW)
    edit("src/main.py", GOAL3_METRIC_OLD, GOAL3_METRIC_NEW)
    edit("src/main.py", GOAL3_CHUNK_OLD, GOAL3_CHUNK_NEW)
    edit("src/main.py", "os_store.wait_until_searchable(expected_count=1)", "os_store.wait_until_searchable(expected_count=2)")


GOAL4_OLD = '''        """Hybrid search over BM25 (keyword) and kNN (vector), returning top_k docs."""
        # TODO(DIY-3): this hybrid query returns hits without a usable fused `score`.
        # Repair the method so BM25 and kNN results are combined into a single
        # ranked list where every returned hit carries a numeric `score`.
        body = {"size": top_k, "query": {"bool": {"should": [
            {"match": {"text": query_text}},
            {"knn": {"embedding": {"vector": query_vector, "k": top_k}}},
        ]}}}
        hits = self.client.search(index=INDEX_NAME, body=body)["hits"]["hits"]
        return [self._to_doc(h) for h in hits]'''
GOAL4_NEW = '''        """Hybrid search: BM25 and kNN run separately, fused with Reciprocal Rank Fusion."""
        pool = max(top_k * 4, 10)
        fused = {}
        for hits in (self._bm25(query_text, pool), self._knn(query_vector, pool)):
            seen = set()
            rank = 0
            for doc in hits:
                cid = doc["chunk_id"]
                if cid in seen:
                    continue
                seen.add(cid)
                rank += 1
                entry = fused.setdefault(cid, {**doc, "score": 0.0})
                entry["score"] += 1.0 / (rrf_k + rank)
        ranked = sorted(fused.values(), key=lambda d: d["score"], reverse=True)
        return ranked[:top_k]'''


def goal4():
    print("Goal 4: hybrid retrieval (RRF)")
    edit("src/opensearch_client.py", GOAL4_OLD, GOAL4_NEW)


GOAL5_OLD = '''    # TODO(DIY-4): guard this tool before it runs the query. Reject anything
    # that is not a genuine read, then reject anything that contains a
    # disallowed clause from the _FORBIDDEN_CYPHER denylist defined above
    # (return a string starting with "Rejected:" so callers see the refusal).
'''
GOAL5_NEW = '''    normalized = " ".join(cypher_query.split()).upper()
    if not normalized.startswith(("MATCH", "OPTIONAL MATCH", "WITH", "UNWIND", "RETURN")):
        return "Rejected: only read queries (MATCH ... RETURN) are allowed."
    if "RETURN" not in normalized:
        return "Rejected: a read query must RETURN a result."
    for token in _FORBIDDEN_CYPHER:
        if token in normalized:
            return f"Rejected: disallowed clause '{token.strip()}'."
'''


def goal5():
    print("Goal 5: graph query guard")
    edit("src/mcp_server.py", GOAL5_OLD, GOAL5_NEW)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("goals", nargs="+", choices=["1", "2", "3", "4", "5"])
    ap.add_argument("--yes", action="store_true", help="confirm the IAM change for goal 2")
    a = ap.parse_args()
    for g in a.goals:
        {"1": goal1, "2": lambda: goal2(a.yes), "3": goal3, "4": goal4, "5": goal5}[g]()
    print("\nNext: run each goal's emit_evidence step and upload the result (see solutions/README.md).")
