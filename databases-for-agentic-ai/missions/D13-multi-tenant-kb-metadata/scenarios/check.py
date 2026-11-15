"""Self-check for D13 (run after a sync): metadata ingested for all partners, filters work, tenants isolated."""
import json
import os
import sys

import boto3

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "common"))
from checks import Db, check, finish, mission_outputs, rows, safe  # noqa: E402

out = mission_outputs(os.path.join(HERE, ".."))
lam = boto3.client("lambda", region_name=out["region"])
agent = boto3.client("bedrock-agent", region_name=out["region"])


def search(tenant, query, model_tenant=None):
    args = {"query": query}
    if model_tenant:
        args["tenant_id"] = model_tenant              # what a manipulated model might send
    r = lam.invoke(FunctionName=out["tool_function"],
                   Payload=json.dumps({"context": {"tenant_id": tenant}, "args": args}).encode())
    body = json.loads(r["Payload"].read())
    if r.get("FunctionError"):
        raise RuntimeError(body.get("errorMessage", body))
    return body


job = agent.list_ingestion_jobs(knowledgeBaseId=out["knowledge_base_id"], dataSourceId=out["data_source_id"],
                                sortBy={"attribute": "STARTED_AT", "order": "DESCENDING"}, maxResults=1)["ingestionJobSummaries"]
stats = job[0].get("statistics", {}) if job else {}
check("latest sync indexed all 6 partner documents without failures",
      job and job[0]["status"] == "COMPLETE" and stats.get("numberOfDocumentsFailed", 1) == 0
      and stats.get("numberOfDocumentsScanned", 0) == 6, json.dumps(stats) if job else "no sync has run")

meta = rows(Db("admin").run("SELECT custom_metadata->>'tenant_id' AS tenant, count(*) AS chunks "
                            "FROM bedrock_kb.d13_chunks GROUP BY 1 ORDER BY 1"))
tenants = {m["tenant"]: m["chunks"] for m in meta}
check("every chunk carries a tenant_id (all 3 partners)", None not in tenants and len(tenants) == 3, json.dumps(tenants))

for tenant, query, expect in [("north-trail", "How many days do I have to return unused items?", "45 days"),
                              ("coastline", "When does the hiking club meet?", "Saturdays"),
                              ("peak-gear", "How long is the return window?", "60 days")]:
    res, err = safe(search, tenant, query)
    hits = (res or {}).get("results", [])
    own = hits and all(f"/partners/{tenant}/" in h["source"] for h in hits)
    check(f"{tenant}: filtered search answers from its own documents", own and any(expect in h["text"] for h in hits),
          err or f"{len(hits)} hits: " + ", ".join(h["source"].split("/partners/")[-1] for h in hits))

res, err = safe(search, "north-trail", "What discount do members get on wetsuit repairs?", model_tenant="coastline")
leak = any("/partners/coastline/" in h["source"] for h in (res or {}).get("results", []))
check("the model cannot switch tenants through tool arguments", err is None and not leak,
      err or ("north-trail received coastline documents" if leak else ""))
finish()
