# Mission D9 solution: Uploaded, but never searchable

```bash
patch -p1 < solutions/D9-diy-ingestion-pipeline/fix.patch
./scripts/deploy.sh D9                                     # schema.sql removes duplicates and adds the unique index
python3 missions/D9-diy-ingestion-pipeline/scenarios/upload_docs.py
python3 missions/D9-diy-ingestion-pipeline/scenarios/check.py
```

## Fault 1: the event pattern only matches `.txt`

| | |
|---|---|
| Symptom | No Lambda invocations, and an empty table |
| Fix | `object.key = [{ suffix = ".md" }, { suffix = ".txt" }]`. Entries in an EventBridge pattern array are ORed |

## Fault 2: chunks are larger than the embedding model accepts

| | |
|---|---|
| Symptom | The five small documents arrive as one chunk each. The handbook fails with a Bedrock `ValidationException` (input too long) |
| Root cause | `CHUNK_CHARS = 60000` treats a whole document as one chunk. Titan V2 accepts up to 8,192 tokens or 50,000 characters, and huge chunks dilute similarity anyway: a 60 KB vector "means" everything and nothing |
| Fix | 2,000-character chunks with 200 characters of overlap (env `CHUNK_CHARS`/`CHUNK_OVERLAP`). The handbook becomes 36 chunks, and the Lyon store fact becomes the top hit for its question |

## Fault 3: ingestion isn't idempotent

| | |
|---|---|
| Symptom | Each upload or retry adds another copy of every chunk. After the shorter revision, the old "Refund timing" chunks are still there |
| Fix | Embed all chunks first, then **in one Data API transaction** `DELETE … WHERE doc_key = :k` and `batch_execute_statement` the new chunks, then commit. A `UNIQUE (doc_key, chunk_no)` index guards the invariant, and `schema.sql` removes duplicates left by the broken version |

## Debrief answers

1. Small chunks give precise matches and cheap embeddings, but less context per hit. Large chunks give more context but blurry vectors and model limits.
   Overlap stops facts being split across a boundary. 10–20 % is typical.
2. A shorter revision has fewer chunks. An upsert per chunk would leave the old tail behind, so the document is the unit of replacement.
   The transaction means readers never see a half-ingested document.
3. A second rule on `Object Deleted` that runs `DELETE … WHERE doc_key = :k`. Or keep a manifest and periodically reconcile S3 against the table.
4. Use a Knowledge Base for standard document Q&A with managed parsing, chunking strategies, syncs and metadata filters. Use do-it-yourself when you need
   custom chunking or parsing, joins with your own tables, custom metadata columns, or tight control over cost and latency (D10–D12).
