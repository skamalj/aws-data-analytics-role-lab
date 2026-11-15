"""C4 check: the three dashboard queries in sql/dashboard.sql are correct and each runs in < 5 s (Athena engine time)."""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "common"))
from lh import Athena, check, finish, safe  # noqa: E402

EXPECTED = {
    "Q1": {"NA": 473927277.23, "EU": 467457157.13, "APAC": 421577113.98, "LATAM": 431496039.08},
    "Q2": [("P106", 22555301.84), ("P114", 22554801.84), ("P118", 22554753.84)],
    "Q3": (1124387.56, 4444),
}
a = Athena()
text = open(os.path.join(HERE, "..", "sql", "dashboard.sql")).read()
queries = {m.group(1): m.group(2).strip().rstrip(";") for m in re.finditer(r"-- (Q\d)[^\n]*\n(.*?)(?=\n-- Q\d|\Z)", text, re.S)}

f = a.rows('SELECT count(*) AS files, avg(file_size_in_bytes) AS avg_bytes FROM riverbend_lakehouse."sales$files"')[0]
check("the table is compacted (<= 400 data files)", int(f["files"]) <= 400, f"{f['files']} files, avg {float(f['avg_bytes'] or 0) / 1e6:.2f} MB")
s = a.rows('SELECT count(*) AS n FROM riverbend_lakehouse."sales$snapshots"')[0]
check("old snapshots are expired (<= 3 snapshots)", int(s["n"]) <= 3, f"{s['n']} snapshots")

full = a.stats("SELECT sum(amount) FROM riverbend_lakehouse.sales")
for q in ("Q1", "Q2", "Q3"):
    sql = queries.get(q)
    if not sql:
        check(f"{q} present in sql/dashboard.sql", False)
        continue
    st, err = safe(a.stats, sql)
    rows, err2 = safe(a.rows, sql)
    if q == "Q1":
        got = {r["region"]: float(r["revenue"]) for r in rows or []}
        ok = set(got) == set(EXPECTED[q]) and all(abs(got[k] - v) < 1 for k, v in EXPECTED[q].items())
    elif q == "Q2":
        got = [(r["product_id"], float(r["revenue"])) for r in rows or []]
        ok = len(got) == 3 and all(g[0] == e[0] and abs(g[1] - e[1]) < 1 for g, e in zip(got, EXPECTED[q]))
    else:
        got = (float(rows[0]["revenue"]), int(rows[0]["sales"])) if rows else None
        ok = got is not None and abs(got[0] - EXPECTED[q][0]) < 1 and got[1] == EXPECTED[q][1]
    check(f"{q} returns the right answer", ok, err or err2 or ("" if ok else f"got {got}"))
    if st:
        check(f"{q} runs in < 5 s", st["engine_ms"] < 5000, f"{st['engine_ms']} ms, {st['scanned'] / 1e6:.1f} MB scanned")
        if q in ("Q1", "Q3"):
            check(f"{q} prunes partitions (scans < 40% of the table)", st["scanned"] < 0.4 * full["scanned"],
                  f"{st['scanned'] / max(full['scanned'], 1):.0%} of a full scan")
finish()
