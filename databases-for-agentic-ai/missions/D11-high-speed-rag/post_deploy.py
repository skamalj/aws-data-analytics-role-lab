"""Embed docs/*.md into knowledge.d11_chunks at the dimension the column declares (run by ./scripts/deploy.sh D11)."""
import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "common"))
from checks import rows  # noqa: E402
from dbsql import Db  # noqa: E402
from embed import chunk_markdown, embed, to_pgvector  # noqa: E402

db = Db("admin")
os.environ.setdefault("AWS_REGION", db.o["region"])
dims = rows(db.run("SELECT atttypmod AS dims FROM pg_attribute WHERE attrelid = 'knowledge.d11_chunks'::regclass "
                   "AND attname = 'embedding'"))[0]["dims"]
n = 0
for path in sorted(glob.glob(os.path.join(HERE, "docs", "*.md"))):
    for i, chunk in enumerate(chunk_markdown(open(path).read())):
        db.run("INSERT INTO knowledge.d11_chunks (doc, chunk_no, content, embedding) VALUES (:d, :n, :c, CAST(:v AS vector))",
               [{"name": "d", "value": {"stringValue": os.path.basename(path)}}, {"name": "n", "value": {"longValue": i}},
                {"name": "c", "value": {"stringValue": chunk}}, {"name": "v", "value": {"stringValue": to_pgvector(embed(chunk, dims))}}])
        n += 1
print(f"  embedded {n} passages at {dims} dimensions")
