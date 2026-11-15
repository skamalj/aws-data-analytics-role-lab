"""Self-check for mission D8: correct results, index-backed plans, and p95 latency under 150 ms per tool."""
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "common"))
from checks import Db, check, finish, invoke_tool, mission_outputs, rows, safe  # noqa: E402

out = mission_outputs(os.path.join(HERE, ".."))
fn, region = out.get("tool_function", ""), out.get("region")
admin = Db("admin")


def tool(name, args):
    return invoke_tool(fn, name, args, target="catalog", region=region)


# 1. correctness
r, err = safe(tool, "search_products", {"query": "waterproof", "category": "Apparel", "max_price": 150, "limit": 10})
res = (r or {}).get("results") or []
ok = r and not r.get("error") and 0 < len(res) <= 10 and all(x["category"] == "Apparel" and float(x["price"]) <= 150 for x in res)
check("search_products('waterproof', Apparel, <=150) returns filtered results", ok, err or (r or {}).get("error") or f"{len(res)} rows")
check("search_products returns only the columns it needs", res and all("embedding" not in x and "description" not in x for x in res))
r, err = safe(tool, "similar_products", {"product_id": "X012345"})
check("similar_products returns 5 neighbours", r and len(r.get("results") or []) == 5, err or (r or {}).get("error") or "")

# 2. plans: can the indexes serve the tools' query shapes?
def explain(sql):
    resp = admin.run("EXPLAIN (COSTS OFF) " + sql)
    return "\n".join(str(list(v[0].values())[0]) for v in resp["records"])


idx = rows(admin.run("SELECT indexname, indexdef FROM pg_indexes WHERE schemaname = 'catalog' AND tablename = 'products'"))
kinds = {"trgm": [i["indexname"] for i in idx if "gin_trgm_ops" in i["indexdef"]],
         "hnsw": [i["indexname"] for i in idx if "hnsw" in i["indexdef"].lower()],
         "btree": [i["indexname"] for i in idx if "(category" in i["indexdef"]]}
plans = [
    ("text search (name OR description) uses trigram indexes", "trgm",
     "SELECT product_id FROM catalog.products WHERE (name ILIKE '%kestrel storm jacket%' "
     "OR description ILIKE '%kestrel storm jacket%') AND in_stock ORDER BY rating DESC LIMIT 10"),
    ("category browse uses a (category, price) index", "btree",
     "SELECT product_id FROM catalog.products WHERE category = 'Footwear' AND price <= 60 AND in_stock ORDER BY price LIMIT 20"),
    ("similar products uses an HNSW index", "hnsw",
     "SELECT product_id FROM catalog.products ORDER BY embedding <=> "
     "(SELECT embedding FROM catalog.products WHERE product_id = 'X012345') LIMIT 5"),
]
for name, kind, sql in plans:
    p, err = safe(explain, sql)
    used = [n for n in kinds[kind] if p and n in p]
    seq = p is not None and "Seq Scan on products" in p
    check(name, bool(used) and not seq, err or ("uses " + ", ".join(used) if used else
                                              "no suitable index in the plan: " + " | ".join(l.strip() for l in (p or "").splitlines() if "Scan" in l)))

# 3. latency SLA (warm calls, as measured by the tool itself)
cases = {"search_products": {"query": "kestrel storm jacket", "limit": 10},
         "browse_category": {"category": "Footwear", "max_price": 60},
         "similar_products": {"product_id": "X054321"}}
for name, args in cases.items():
    tool(name, args)                                   # warm-up
    times = []
    for _ in range(8):
        r, err = safe(tool, name, args)
        times.append((r or {}).get("db_ms", 99999) if r and not r.get("error") else 99999)
    p95 = sorted(times)[int(len(times) * 0.95) - 1]
    check(f"{name} p95 < 150 ms", p95 < 150, f"p95 {p95} ms, median {statistics.median(times)} ms")
finish()
