"""Self-check for D11: consistent 512-d vectors, working cache, warm-start reuse, and a cached answer under 150 ms."""
import json
import os
import sys
import uuid

import boto3

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "common"))
from checks import Db, check, finish, mission_outputs, rows, safe  # noqa: E402

out = mission_outputs(os.path.join(HERE, ".."))
lam = boto3.client("lambda", region_name=out["region"])


def ask(q):
    r = lam.invoke(FunctionName=out["tool_function"], Payload=json.dumps({"question": q}).encode())
    body = json.loads(r["Payload"].read())
    if r.get("FunctionError"):
        raise RuntimeError(body.get("errorMessage", body))
    return body


db = Db("admin")
d = rows(db.run("SELECT min(vector_dims(embedding)) AS lo, max(vector_dims(embedding)) AS hi, count(*) AS n FROM knowledge.d11_chunks"))[0]
env = lam.get_function_configuration(FunctionName=out["tool_function"])["Environment"]["Variables"]
check("stored vectors, column and query embeddings all use 512 dimensions",
      d["lo"] == d["hi"] == 512 and env.get("EMBED_DIMENSIONS") == "512", f"stored {d['lo']}-{d['hi']} (n={d['n']}), query {env.get('EMBED_DIMENSIONS')}")

question = f"How do I bring back the water repellency of my rain jacket? [{uuid.uuid4().hex[:6]}]"
first, err = safe(ask, question)
check("fast_answer returns passages", first and first.get("passages"), err or "")
if first:
    check("the right document comes first", first["passages"][0]["doc"] == "rain-shell-jacket-care.md", first["passages"][0]["doc"])
    second, err = safe(ask, question)
    t = (second or {}).get("timings", {})
    check("repeating a question hits the embedding cache", t.get("cache_hit") is True, err or json.dumps(t))
    check("warm invocations reuse SDK clients (client_init_ms < 5)", t.get("client_init_ms", 999) < 5, f"{t.get('client_init_ms')} ms")
    totals = [ask(question)["timings"]["total_ms"] for _ in range(5)]
    check("cached answers in < 150 ms (p95 of 5 warm calls)", max(totals) < 150, f"{sorted(totals)} ms")
finish()
