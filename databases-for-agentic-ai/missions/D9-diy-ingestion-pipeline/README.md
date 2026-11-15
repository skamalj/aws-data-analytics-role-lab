# Mission D9: Uploaded, but never searchable

**Based on:** the do-it-yourself RAG pattern in [aws-samples/rag-with-amazon-postgresql-using-pgvector](https://github.com/aws-samples/rag-with-amazon-postgresql-using-pgvector) (load, chunk, embed and store in pgvector yourself, rather than with a Knowledge Base)
**Skills:** S3 → EventBridge → Lambda ingestion, event pattern matching, chunk sizing vs embedding-model input limits, idempotent re-ingestion with Data API transactions, uniqueness constraints
**Time:** 45 minutes  |  **Needs:** `./scripts/deploy.sh base`, then `./scripts/deploy.sh D9`

## Situation

Some teams want full control over how documents become vectors: their own chunking, their own
metadata, their own schema. Riverbend's content team now publishes documents to an S3 bucket.
Each upload is meant to trigger [`lambdas/ingest.py`](lambdas/ingest.py), which splits the document into chunks,
embeds each chunk with **Titan Text Embeddings V2** and stores it in `knowledge.d9_chunks`, logging in as `bedrock_kb_user`.
The document set includes a new **64 KB staff handbook**, and documents are re-published regularly.

```
s3://riverbend-d9-docs-*/library/*.md ─(EventBridge: Object Created)─► Lambda riverbend-d9-ingest
                                         ─ chunk ─ Titan V2 ─► Data API ─► knowledge.d9_chunks (vector(1024), HNSW)
```

## Symptoms

```bash
python3 missions/D9-diy-ingestion-pipeline/scenarios/upload_docs.py    # uploads 6 docs, then a shorter revision of one
python3 missions/D9-diy-ingestion-pipeline/scenarios/check.py
```

## Objectives

1. Every document the team uploads (Markdown or plain text) is ingested automatically.
2. Large documents are split into chunks the embedding model accepts and that retrieve precisely.
3. Re-uploading a document **replaces** its chunks: no duplicates, and no leftovers from an older, longer version. This holds even when the Lambda is retried.
4. Keep Titan V2 at 1024 dimensions, and keep the writer identity `bedrock_kb_user`.

## Done when

```
PASS  all 6 uploaded documents are ingested
PASS  the 64 KB staff handbook is ingested in small chunks (>= 25 chunks, each <= 3,000 chars)
PASS  no duplicate chunks (one row per doc_key + chunk_no)
PASS  re-uploading a document replaces its chunks (no stale text from the old version)
PASS  a specific handbook fact is retrievable
```

After fixing, run `upload_docs.py` again: it's the re-upload that proves objective 3.

## Investigation toolkit

```bash
aws logs tail /aws/lambda/riverbend-d9-ingest --since 15m
aws events describe-rule --name riverbend-d9-document-uploaded --query EventPattern --output text
aws s3 ls s3://$(terraform -chdir=missions/D9-diy-ingestion-pipeline/terraform output -raw docs_bucket)/library/
python3 common/dbsql.py --sql "SELECT doc_key, count(*), count(DISTINCT chunk_no), max(length(content)) FROM knowledge.d9_chunks GROUP BY doc_key"
```

## Hint ladder

<details><summary>Hint 1: nothing happens at all</summary>Did the Lambda run? Compare the rule's event pattern with the object keys that were uploaded.</details>
<details><summary>Hint 2: the handbook fails, the small documents work</summary>Read the Bedrock error in the Lambda log. Titan V2 accepts at most 8,192 tokens / 50,000 characters. And even below that limit, what does one 60,000-character "chunk" do to retrieval quality?</details>
<details><summary>Hint 3: counts grow on every upload</summary>A plain <code>INSERT</code> per chunk isn't idempotent. EventBridge → Lambda is asynchronous, and failed invocations are retried. How do you replace a document's chunks in one step? (The Data API supports transactions.)</details>

## Debrief questions

1. What are the trade-offs of chunk size and overlap?
2. Why delete-then-insert in a transaction, rather than an upsert per chunk?
3. What would you add for deletions, when a document is removed from S3?
4. When is a Bedrock Knowledge Base (D2) the better choice than this do-it-yourself pipeline, and when isn't it?
