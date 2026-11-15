"""Self-check for mission D6. Run after ./scripts/deploy.sh D6 and ingest.py."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "common"))
from checks import Db, check, finish, invoke_tool, mission_outputs, plan, rows, safe  # noqa: E402

out = mission_outputs(os.path.join(HERE, ".."))
admin, app = Db("admin"), Db("app")

r, err = safe(admin.run, "SELECT count(*) AS n, count(DISTINCT doc) AS docs, min(vector_dims(embedding)) AS dims FROM knowledge.doc_chunks")
stats = rows(r)[0] if r else {}
check("documents are ingested (5 docs, 1024-d vectors)", stats.get("docs") == 5 and stats.get("dims") == 1024,
      err or f"{stats}")

_, err = safe(app.run, "SELECT count(*) FROM knowledge.doc_chunks")
check("trail_desk_app can read knowledge.doc_chunks", err is None, err or "")

_, err = safe(app.run, "DELETE FROM knowledge.doc_chunks WHERE false")
check("trail_desk_app cannot modify knowledge.doc_chunks", err is not None, "" if err else "DELETE was allowed")

p, err = safe(plan, admin, "SELECT id FROM knowledge.doc_chunks ORDER BY embedding <=> "
                           "(SELECT embedding FROM knowledge.doc_chunks ORDER BY id LIMIT 1) LIMIT 4")
check("the cosine search (<=>) can use the HNSW index", p is not None and "doc_chunks_embedding_idx" in p,
      err or ("plan uses: " + " / ".join(l.strip() for l in p.splitlines() if "Scan" in l)))

res, err = safe(invoke_tool, out.get("tool_function", ""), "search_docs",
                {"query": "How do I restore the water repellency of my rain jacket?"}, target="docs")
top = ((res or {}).get("passages") or [{}])[0]
check("search_docs returns the rain-jacket care guide first", top.get("doc") == "rain-shell-jacket-care.md",
      err or (res or {}).get("error") or f"top hit: {top.get('doc')}")
finish()
