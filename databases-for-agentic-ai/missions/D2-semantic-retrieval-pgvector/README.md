# Mission D2: Manuals in, nothing out

**Skills:** Amazon Bedrock Knowledge Bases with **Aurora PostgreSQL + pgvector** as the vector store, vector dimensions vs embedding models, KB field mapping, HNSW and GIN indexes, the KB's database identity and IAM role, ingestion (sync) jobs
**Time:** 45–60 minutes  |  **Needs:** `./scripts/deploy.sh base`, then `./scripts/deploy.sh D2`

## Situation

The architects want product manuals to live **next to the operational data** in the shared Aurora
cluster rather than in a separate vector service. One database, one backup and security model,
and SQL joins between chunks and products later.

- [`db/kb_schema.sql`](db/kb_schema.sql) creates the pgvector table `bedrock_kb.manual_chunks` (run by `setup.py` on every deploy).
- The **Bedrock Knowledge Base** embeds the five manuals with **Titan Text Embeddings V2 (1024 dimensions)** and stores the chunks in that table,
  logging in as `bedrock_kb_user` (credentials in the `riverbend-db-kb-*` secret) through the RDS Data API.
- Trail Desk searches with its `search_manuals` tool (`Retrieve`).

```
s3://riverbend-d2-docs-*/manuals/*.md ─► KB riverbend-d2-manuals ─(Titan V2, 1024-d)─► Data API as bedrock_kb_user ─► bedrock_kb.manual_chunks
Trail Desk ── search_manuals ──► Retrieve ──► pgvector similarity search (HNSW) ──► passages
```

## Symptom

```bash
./scripts/deploy.sh D2
```

The deployment fails when it creates the knowledge base. Fix that, and the next error appears, either
at creation or when you run a sync:

```bash
$(terraform -chdir=missions/D2-semantic-retrieval-pgvector/terraform output -raw sync_command)
```

## Objectives

1. The knowledge base deploys, and a sync ingests all **5** documents with **0** failures.
2. `bedrock_kb.manual_chunks` contains the chunks, with 1024-dimension embeddings.
3. Trail Desk answers from the manuals.
4. The KB role reads **only** its own secret, and `bedrock_kb_user` can only touch its own table.
5. Keep Titan V2 at 1024 dimensions. Fix the store to match the model, not the other way round.

## Done when

```bash
python3 common/dbsql.py --sql "SELECT count(*), vector_dims(embedding) FROM bedrock_kb.manual_chunks GROUP BY 2"   # >= 5 rows, 1024
python3 common/chat.py D2 "How do I bring back the water repellency on my Rain Shell Jacket?"   # wash 30C, tumble dry LOW 20 min, spray-on DWR ...
python3 common/chat.py D2 "What is the warranty on an expedition pack?"                          # lifetime
```

## Investigation toolkit

```bash
aws bedrock-agent list-ingestion-jobs --knowledge-base-id <kb> --data-source-id <ds> --query 'ingestionJobSummaries[0]'
aws bedrock-agent get-ingestion-job --knowledge-base-id <kb> --data-source-id <ds> --ingestion-job-id <job> --query 'ingestionJob.[status,statistics,failureReasons]'
python3 common/dbsql.py --sql "SELECT column_name, data_type, udt_name FROM information_schema.columns WHERE table_schema='bedrock_kb' AND table_name='manual_chunks'"
python3 common/dbsql.py --sql "SELECT format_type(atttypid, atttypmod) FROM pg_attribute WHERE attrelid='bedrock_kb.manual_chunks'::regclass AND attname='embedding'"
python3 common/dbsql.py --sql "SELECT indexdef FROM pg_indexes WHERE schemaname='bedrock_kb'"
aws iam get-role-policy --role-name <kb_role_name> --policy-name kb-access
```

## Hint ladder

<details><summary>Hint 1: how does the KB get into the database?</summary>

`credentials_secret_arn` tells Bedrock which secret to log in with. Bedrock reads it **as the KB's IAM role**. Which actions does that role have?
</details>

<details><summary>Hint 2: the KB and the table must agree on names</summary>

Compare every name in `field_mapping` with the table's actual column names.
</details>

<details><summary>Hint 3: the KB and the table must agree on dimensions</summary>

What length of vector does Titan Text Embeddings V2 produce with `dimensions = 1024`? What does `vector(N)` enforce? Can you `ALTER` the type of a column that already has an HNSW index and data, or is it simpler to rebuild?
</details>

## Red herrings

- `rds:DescribeDBClusters` and the `rds-data:*` actions are correct.
- Chunking (300 tokens, 15 % overlap) is fine for these documents.
- The cluster may be auto-paused. `setup.py` wakes it before Terraform runs. If a sync fails with a resuming or connection error, just run it again.

## Debrief questions

1. Which indexes does a Bedrock KB on pgvector rely on, and what does each one serve?
2. You switch to an embedding model with 512 dimensions. What has to change, and what has to be re-done?
3. Pros and cons of keeping vectors in the operational Aurora cluster, compared with a dedicated store (S3 Vectors, OpenSearch Serverless).
4. How would you enforce *document-level* authorization (for example, staff-only manuals) on top of `Retrieve`?
