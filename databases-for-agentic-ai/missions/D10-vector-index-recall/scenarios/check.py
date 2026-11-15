"""Self-check for D10: recall of both indexes against exact search, rows returned, and query time - as trail_desk_app."""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "common"))
from checks import Db, check, finish, in_transaction, rows  # noqa: E402

admin, app = Db("admin"), Db("app")
QUERIES = [11, 222, 3333, 4444, 5555, 6666, 7777, 8888, 9999, 12345, 13579, 17171]
SQL = "SELECT id FROM vectors.{t} ORDER BY embedding <=> (SELECT embedding FROM vectors.{t} WHERE id = {q}) LIMIT {k}"


def ids(resp):
    return [r["id"] for r in rows(resp)]


def exact(t, q, k):   # brute force: the ground truth
    return ids(in_transaction(admin, ["SET LOCAL enable_indexscan = off", "SET LOCAL enable_bitmapscan = off",
                                      SQL.format(t=t, q=q, k=k)]))


def recall(t, k):
    hits, returned = 0, []
    for q in QUERIES:
        got = ids(app.run(SQL.format(t=t, q=q, k=k)))
        returned.append(len(got))
        hits += len(set(got) & set(exact(t, q, k)))
    return hits / (len(QUERIES) * k), min(returned)


r, n = recall("reviews_ivf", 10)
check("IVFFlat: recall@10 >= 0.95 for the agent's top-10 lookups", r >= 0.95, f"recall {r:.2f}")
r, n = recall("reviews_hnsw", 100)
check("HNSW: top-100 candidate export returns 100 rows", n == 100, f"only {n} rows returned")
check("HNSW: recall@100 >= 0.95", r >= 0.95, f"recall {r:.2f}")

for t in ("reviews_ivf", "reviews_hnsw"):
    k = 10 if t == "reviews_ivf" else 100
    plan = "\n".join(str(list(v[0].values())[0]) for v in app.run("EXPLAIN (ANALYZE) " + SQL.format(t=t, q=4242, k=k))["records"])
    ms = float(re.search(r"Execution Time: ([\d.]+) ms", plan).group(1))
    check(f"{t}: uses its vector index and runs in < 25 ms", f"{t}_idx" in plan and ms < 25, f"{ms:.1f} ms")

settings = {r["setting"]: r["value"] for r in rows(app.run(
    "SELECT 'probes' AS setting, current_setting('ivfflat.probes') AS value UNION ALL "
    "SELECT 'ef_search', current_setting('hnsw.ef_search')"))}
print(f"\ntrail_desk_app session settings: {settings}")
finish()
