"""Self-check for D12: tenant isolation under row-level security, and complete top-k results per tenant."""
import json
import os
import sys

import boto3

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "common"))
from checks import Db, check, finish, mission_outputs, rows, safe  # noqa: E402

out = mission_outputs(os.path.join(HERE, ".."))
lam = boto3.client("lambda", region_name=out["region"])


def search(tenant, doc_id, k=10):
    r = lam.invoke(FunctionName=out["tool_function"], Payload=json.dumps({"tenant_id": tenant, "doc_id": doc_id, "k": k}).encode())
    body = json.loads(r["Payload"].read())
    if r.get("FunctionError"):
        raise RuntimeError(body.get("errorMessage", body))
    return body["results"]


leaks, short = [], []
for tenant, doc in [("tenant-01", 21), ("tenant-07", 27), ("tenant-13", 33), ("tenant-01", 41), ("tenant-07", 47)] * 2:
    res, err = safe(search, tenant, doc)
    if err:
        short.append(f"{tenant}: {err[:120]}")
        continue
    leaks += [f"{tenant} saw {r['tenant_id']}" for r in res if r["tenant_id"] != tenant]
    if len(res) != 10:
        short.append(f"{tenant}/{doc}: {len(res)} rows")
check("no tenant ever sees another tenant's documents (10 searches)", not leaks, "; ".join(sorted(set(leaks))[:4]))
check("every search returns the full top 10 of the caller's own tenant", not short, "; ".join(short[:4]))

res, err = safe(search, "tenant-01", 22)      # document 22 belongs to tenant-02
check("asking for another tenant's document reveals nothing of that tenant",
      err is None and all(r["tenant_id"] == "tenant-01" for r in res), err or "")

t = rows(Db("admin").run("SELECT tableowner, c.relrowsecurity AS rls, c.relforcerowsecurity AS force_rls "
                         "FROM pg_tables JOIN pg_class c ON c.relname = tablename "
                         "WHERE schemaname = 'saas' AND tablename = 'tenant_docs'"))[0]
check("row-level security cannot be bypassed by the service identity",
      t["rls"] and (t["tableowner"] != "saas_app" or t["force_rls"]), json.dumps(t))
finish()
