"""
Local grader: reads the evidence you uploaded to s3://$EVIDENCE_BUCKET/$EVIDENCE_PREFIX/ (as the lab's grader does) and,
for goal 2, checks IAM directly. Run from the project root:

    python scripts/check_evidence.py            # all goals
    python scripts/check_evidence.py 1 3        # selected goals
"""
import json
import os
import sys

import boto3
from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT, ".env"))
REGION = os.getenv("AWS_REGION", "us-east-1")
BUCKET = os.getenv("EVIDENCE_BUCKET", "")
PREFIX = os.getenv("EVIDENCE_PREFIX", "evidence")
_results = []


def check(name, ok, detail=""):
    _results.append(bool(ok))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  -- {detail}" if detail and not ok else ""))


def evidence(name):
    try:
        body = boto3.client("s3", region_name=REGION).get_object(Bucket=BUCKET, Key=f"{PREFIX}/{name}")["Body"].read()
        return json.loads(body)
    except Exception as e:  # noqa: BLE001
        print(f"  (no s3://{BUCKET}/{PREFIX}/{name}: {type(e).__name__})")
        return None


def goal1():
    print("Goal 1: memory tools and turn order (mcp_tools_result.json)")
    e = evidence("mcp_tools_result.json") or {}
    check("append_turn is registered on the MCP server", e.get("append_turn_registered") is True)
    check("get_session is registered on the MCP server", e.get("get_session_registered") is True)
    check("get_session('s-demo') returns turns oldest first: [1, 2, 3]", e.get("session_order") == [1, 2, 3], f"got {e.get('session_order')}")


def goal2():
    print("Goal 2: IAM ownership boundary (checked live in IAM)")
    role, table = os.getenv("MCP_VECTOR_ROLE_NAME", ""), os.getenv("SESSION_TABLE_ARN", "")
    iam = boto3.client("iam", region_name=REGION)
    arn = iam.get_role(RoleName=role)["Role"]["Arn"]
    names = iam.list_role_policies(RoleName=role)["PolicyNames"]
    check("the inline policy vector-memory-leak is gone", "vector-memory-leak" not in names, f"inline policies: {names}")
    check("the role's other policy (vector-store-access) is untouched", "vector-store-access" in names, f"inline policies: {names}")
    r = iam.simulate_principal_policy(PolicySourceArn=arn, ActionNames=["dynamodb:GetItem", "dynamodb:Query"], ResourceArns=[table])
    dec = {x["EvalActionName"]: x["EvalDecision"] for x in r["EvaluationResults"]}
    check("simulated GetItem / Query on claims-sessions are denied", all(v != "allowed" for v in dec.values()), f"{dec}")


def goal3():
    print("Goal 3: knowledge graph ontology (ontology_result.json)")
    e = evidence("ontology_result.json") or {}
    rows = {r.get("entity_id"): r for r in e.get("traversal", [])}
    nt, af = rows.get("ent_nexus_tower", {}), rows.get("ent_atlantic_freight", {})
    check("Nexus Tower -> CommercialPropertyPolicy", nt.get("class_name") == "CommercialPropertyPolicy", f"{nt}")
    check("Nexus Tower -> solvency_ii_ratio", nt.get("applicable_metrics") == ["solvency_ii_ratio"], f"{nt}")
    check("Atlantic Freight -> MarineCargoPolicy", af.get("class_name") == "MarineCargoPolicy", f"{af}")
    check("Atlantic Freight -> cargo_loss_ratio", af.get("applicable_metrics") == ["cargo_loss_ratio"], f"{af}")


def goal4():
    print("Goal 4: hybrid retrieval (retrieval_result.json, comparison_results.json)")
    e = evidence("retrieval_result.json") or {}
    probe = e.get("rrf_probe", [])
    check("the RRF probe returned hits", len(probe) >= 1, f"{probe}")
    scores = [h.get("score") for h in probe]
    check("every hit carries a numeric fused score", probe and all(isinstance(s, (int, float)) and s > 0 for s in scores), f"{scores}")
    check("scores are RRF-scale (each list adds at most 1/61) and ranked", probe and all(s <= 2 / 61 + 1e-9 for s in scores)
          and scores == sorted(scores, reverse=True), f"{scores}")
    check("the Nexus Tower chunk ranks first", probe and probe[0].get("chunk_id") == "doc_chunk_101", f"{probe}")
    c = evidence("comparison_results.json") or {}
    for store in ("opensearch", "pgvector"):
        s = c.get(store, {})
        check(f"benchmark: {store} indexed both chunks and returned hits", s.get("doc_count", 0) >= 2 and s.get("relevance_at_k", 0) > 0, f"{s}")


def goal5():
    print("Goal 5: graph query guard (cypher_guard_result.json)")
    e = evidence("cypher_guard_result.json") or {}
    check("a genuine read query is admitted", e.get("allowed_query_ok") is True)
    check("CALL dbms.components() is rejected", e.get("blocked_query_rejected") is True)


if __name__ == "__main__":
    if not BUCKET:
        sys.exit("EVIDENCE_BUCKET not set: create .env with scripts/make_env.py")
    goals = {"1": goal1, "2": goal2, "3": goal3, "4": goal4, "5": goal5}
    for g in (sys.argv[1:] or list(goals)):
        goals[g]()
        print()
    print(f"{sum(_results)}/{len(_results)} checks passed")
    sys.exit(0 if _results and all(_results) else 1)
