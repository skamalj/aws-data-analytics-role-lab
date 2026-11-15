"""Self-check for mission D9 (run after scenarios/upload_docs.py)."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "common"))
from checks import Db, check, finish, rows, safe  # noqa: E402
from embed import embed, to_pgvector  # noqa: E402

db = Db("admin")
os.environ.setdefault("AWS_REGION", db.o["region"])
per_doc = {r["doc_key"]: r for r in rows(db.run(
    "SELECT doc_key, count(*) AS chunks, max(length(content)) AS longest, count(DISTINCT chunk_no) AS distinct_no "
    "FROM knowledge.d9_chunks GROUP BY doc_key"))}
check("all 6 uploaded documents are ingested", len(per_doc) == 6, ", ".join(sorted(per_doc)) or "nothing ingested")
hb = per_doc.get("library/staff-handbook.md", {})
check("the 64 KB staff handbook is ingested in small chunks (>= 25 chunks, each <= 3,000 chars)",
      hb.get("chunks", 0) >= 25 and (hb.get("longest") or 10**9) <= 3000, f"{hb}")
dups = [k for k, r in per_doc.items() if r["chunks"] != r["distinct_no"]]
check("no duplicate chunks (one row per doc_key + chunk_no)", not dups, ", ".join(dups))
rp = rows(db.run("SELECT count(*) AS n, bool_or(content ILIKE '%Refund timing%') AS stale FROM knowledge.d9_chunks "
                 "WHERE doc_key = 'library/returns-policy.md'"))[0]
check("re-uploading a document replaces its chunks (no stale text from the old version)", rp["n"] and not rp["stale"], f"{rp}")
q = to_pgvector(embed("When does the Lyon store close on Saturdays and when is its stock count?"))
top, err = safe(db.run, "SELECT doc_key, content FROM knowledge.d9_chunks ORDER BY embedding <=> CAST(:q AS vector) LIMIT 1",
                [{"name": "q", "value": {"stringValue": q}}])
hit = rows(top)[0] if top and top.get("records") else {}
check("a specific handbook fact is retrievable", "19:00" in (hit.get("content") or ""), err or f"top hit: {hit.get('doc_key')}")
finish()
