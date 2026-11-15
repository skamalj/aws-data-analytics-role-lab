"""Shared helpers for mission self-check scripts (PASS/FAIL lines, Data API transactions, tool invocation)."""
import base64
import json
import os
import subprocess
import sys

import boto3

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "common"))
from dbsql import SECRETS, Db  # noqa: E402

_results = []


def check(name, ok, detail=""):
    _results.append(bool(ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  -- {detail}" if detail else ""), flush=True)
    return ok


def finish():
    print(f"\n{sum(_results)}/{len(_results)} checks passed")
    sys.exit(0 if _results and all(_results) else 1)


def mission_outputs(mission_dir):
    r = subprocess.run(["terraform", f"-chdir={mission_dir}/terraform", "output", "-json"], capture_output=True, text=True)
    return {k: v["value"] for k, v in json.loads(r.stdout or "{}").items()}


def rows(resp):
    cols = [c["name"] for c in resp.get("columnMetadata", [])]
    return [dict(zip(cols, [None if v.get("isNull") else list(v.values())[0] for v in r])) for r in resp.get("records", [])]


def safe(fn, *a, **kw):
    """Run fn, returning (result, None) or (None, 'ErrorType: message')."""
    try:
        return fn(*a, **kw), None
    except Exception as e:  # noqa: BLE001
        return None, f"{type(e).__name__}: {str(e)[:300]}"


def in_transaction(db, statements):
    """Run several statements in ONE Data API transaction (one database session). Returns the last response."""
    tx = db.c.begin_transaction(resourceArn=db.kw["resourceArn"], secretArn=db.kw["secretArn"], database=db.kw["database"])["transactionId"]
    try:
        last = None
        for s in statements:
            sql, params = (s, []) if isinstance(s, str) else s
            last = db.c.execute_statement(sql=sql, parameters=params, includeResultMetadata=True, transactionId=tx, **db.kw)
        db.c.commit_transaction(resourceArn=db.kw["resourceArn"], secretArn=db.kw["secretArn"], transactionId=tx)
        return last
    except Exception:
        db.c.rollback_transaction(resourceArn=db.kw["resourceArn"], secretArn=db.kw["secretArn"], transactionId=tx)
        raise


def plan(db, sql, params=None):
    """EXPLAIN a query with sequential scans discouraged: shows whether an index CAN serve it."""
    r = in_transaction(db, ["SET LOCAL enable_seqscan = off", (f"EXPLAIN (COSTS OFF) {sql}", params or [])])
    return "\n".join(str(list(v[0].values())[0]) for v in r["records"])


def invoke_tool(function_name, tool, args, target="tools", region=None):
    """Invoke a Gateway Lambda target exactly like AgentCore Gateway does."""
    lam = boto3.client("lambda", region_name=region)
    ctx = base64.b64encode(json.dumps({"custom": {"bedrockAgentCoreToolName": f"{target}___{tool}"}}).encode()).decode()
    r = lam.invoke(FunctionName=function_name, ClientContext=ctx, Payload=json.dumps(args).encode())
    body = json.loads(r["Payload"].read() or b"null")
    if r.get("FunctionError"):
        raise RuntimeError(f"Lambda error: {json.dumps(body)[:300]}")
    return body


__all__ = ["check", "finish", "mission_outputs", "rows", "safe", "in_transaction", "plan", "invoke_tool", "Db", "SECRETS", "ROOT"]
