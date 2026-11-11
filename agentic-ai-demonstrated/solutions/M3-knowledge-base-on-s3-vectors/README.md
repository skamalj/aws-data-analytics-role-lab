# Mission 3 solution: The manuals are there, but the agent can't find them

```bash
patch -p1 < solutions/M3-knowledge-base-on-s3-vectors/fix.patch
./scripts/deploy.sh M3                 # replaces the vector index (and with it the knowledge base)
$(terraform -chdir=missions/M3-knowledge-base-on-s3-vectors/terraform output -raw sync_command)
# wait ~1 minute, check statistics, then ask the questions again
```

## Fault 1: the agent may not call `Retrieve`

| | |
|---|---|
| Symptom | `[trace] {"tool_error": "search_manuals", "detail": "AccessDeniedException: … not authorized to perform: bedrock:Retrieve …"}` |
| Where | Agent policy `SearchManuals`: `actions = ["bedrock:RetrieveAndGenerate"]` |
| Root cause | The tool calls **`Retrieve`**, which returns passages that the agent's own model reasons over. `RetrieveAndGenerate` is a separate action: Bedrock retrieves *and* writes the answer with a model you choose. Allowing one doesn't allow the other |
| Fix | `actions = ["bedrock:Retrieve"]` on the knowledge base ARN only |

## Fault 2: the data source looks in the wrong prefix

| | |
|---|---|
| Symptom | The sync finishes `COMPLETE`, but `numberOfDocumentsScanned: 0`. Retrieve returns "No matching passages found" |
| Where | `s3_configuration.inclusion_prefixes = ["manuals/"]`, while the documents are uploaded to `library/` |
| Fix | `inclusion_prefixes = ["library/"]`, or remove the prefix if the bucket holds nothing else |

## Fault 3: the vector index treats chunk text as filterable metadata

| | |
|---|---|
| Symptom | After fix 2, the sync reports documents **failed**. `failureReasons` mention filterable metadata exceeding the size limit |
| Where | `aws_s3vectors_index.manuals` has no `metadata_configuration` |
| Root cause | Bedrock stores the chunk text in `AMAZON_BEDROCK_TEXT` and source metadata in `AMAZON_BEDROCK_METADATA` on every vector. By default all S3 Vectors metadata is **filterable**, and filterable metadata is limited to **2 KB per vector**. 1,000-token chunks are well over that |
| Fix | `metadata_configuration { non_filterable_metadata_keys = ["AMAZON_BEDROCK_TEXT", "AMAZON_BEDROCK_METADATA"] }` |

The metadata configuration is fixed when the index is created, so Terraform **replaces** the index. The knowledge base's storage configuration points at the index ARN, so it's replaced too, and the runtime picks up the new `KB_ID`. In production, plan this as a blue/green swap: build the new index and KB, sync it, then switch the agent over.

## Debrief answers

1. `Retrieve` returns ranked chunks with scores and sources. The agent decides what to do with them,
   for example combining them with tool results or asking a follow-up. `RetrieveAndGenerate` is a
   finished RAG answer from a model Bedrock calls for you. That's convenient for simple Q&A, but it gives an agent less control.
2. Index settings (dimension, distance metric, data type, non-filterable keys) can't be changed after the index is created.
   Changing them means re-embedding everything. You can keep or rebuild a KB, but you must re-sync.
3. Smaller chunks (200–400 tokens) give more precise matches and fit under the filterable limit.
   The trade-off is less context per hit, so you'd retrieve more results. Hierarchical chunking gives you both.
4. OpenSearch Serverless suits hybrid (keyword + vector) search, very high query rates and low-latency
   aggregations. Aurora pgvector suits joining vectors with relational data in SQL.
   S3 Vectors is cheapest for large, infrequently queried corpora where sub-second latency is fine.
