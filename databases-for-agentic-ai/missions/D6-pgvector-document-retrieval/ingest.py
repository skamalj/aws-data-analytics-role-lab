"""
Riverbend's document ingestion job for Trail Desk's pgvector store (run it after deploying):

    python3 missions/D6-pgvector-document-retrieval/ingest.py

Splits every docs/*.md into ~900-character chunks, embeds each chunk with Titan Text
Embeddings V2 and upserts it into knowledge.doc_chunks (as the admin/ingestion identity).
"""
import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "common"))
from dbsql import Db  # noqa: E402
from embed import chunk_markdown, embed, to_pgvector  # noqa: E402

EMBED_DIMENSIONS = 512          # smaller vectors are cheaper to store and faster to search

db = Db("admin")
os.environ.setdefault("AWS_REGION", db.o["region"])
total = 0
for path in sorted(glob.glob(os.path.join(HERE, "docs", "*.md"))):
    doc = os.path.basename(path)
    for n, chunk in enumerate(chunk_markdown(open(path).read())):
        vec = to_pgvector(embed(chunk, EMBED_DIMENSIONS))
        db.run("INSERT INTO knowledge.doc_chunks (doc, chunk_no, content, embedding) "
               "VALUES (:doc, :n, :content, CAST(:v AS vector)) "
               "ON CONFLICT (doc, chunk_no) DO UPDATE SET content = EXCLUDED.content, embedding = EXCLUDED.embedding",
               [{"name": "doc", "value": {"stringValue": doc}}, {"name": "n", "value": {"longValue": n}},
                {"name": "content", "value": {"stringValue": chunk}}, {"name": "v", "value": {"stringValue": vec}}])
        total += 1
    print(f"  {doc}: ingested")
print(f"{total} chunks ingested")
