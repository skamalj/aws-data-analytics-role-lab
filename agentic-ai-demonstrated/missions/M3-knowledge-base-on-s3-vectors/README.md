# Mission 3: The manuals are there, but the agent can't find them

**Skills:** Amazon Bedrock Knowledge Bases, Amazon S3 Vectors, data sources and ingestion (sync) jobs, chunking, agent tool permissions, RAG troubleshooting
**Time:** 50–60 minutes  |  **Deploy:** `./scripts/deploy.sh M3`

## Situation

Customers ask Trail Desk how to care for their gear, and about warranty and return rules. The
answers are in five documents that the product team uploaded to S3. A **Bedrock Knowledge Base**
should embed those documents (Titan Text Embeddings V2, 1024 dimensions) into an **S3 Vectors**
index, which is far cheaper than a vector database cluster for this size. Trail Desk calls the
knowledge base's `Retrieve` API through its `search_manuals` tool.

```
s3://riverbend-m3-docs-*/library/*.md ──(data source "product-library", ingestion job)──► Titan Embed v2
                                                                                         │ 1024-dim vectors + text
                                                     S3 Vectors bucket riverbend-m3-vectors-*, index "manuals" ◄┘
Trail Desk ── search_manuals ──► bedrock-agent-runtime:Retrieve(KB riverbend-m3-manuals) ──► top 4 passages ──► Nova Lite answer
```

Nobody has checked whether the knowledge base actually contains anything.

## Symptom

```bash
python3 common/chat.py M3 "How do I bring back the water repellency on my Rain Shell Jacket?"
```

Trail Desk can't answer from the manuals. Look at the `[trace]` lines.

## Objectives

1. Trail Desk's `search_manuals` tool can query the knowledge base, with least privilege.
2. All **5** documents are ingested, with **0** failed.
3. Answers are grounded in the documents. Check the passages' `source` in `--raw` output.
4. Every fix must be in Terraform. The ingestion job is the only thing you start by hand
   (`terraform output sync_command`).

## Done when

```bash
python3 common/chat.py M3 "How do I bring back the water repellency on my Rain Shell Jacket?"
#   -> wash at 30 C with technical cleaner, tumble dry LOW 20 min, then spray-on DWR if it still wets out ...
python3 common/chat.py M3 "What is the warranty on an expedition pack?"           # -> lifetime
python3 common/chat.py M3 "I used my stove once and don't like it, can I return it?"
#   -> only if defective, within 30 days
aws bedrock-agent list-ingestion-jobs --knowledge-base-id <id> --data-source-id <id> \
  --query 'ingestionJobSummaries[0].statistics'           # numberOfNewDocumentsIndexed: 5, numberOfDocumentsFailed: 0
```

## Investigation toolkit

```bash
terraform -chdir=missions/M3-knowledge-base-on-s3-vectors/terraform output
$(terraform -chdir=missions/M3-knowledge-base-on-s3-vectors/terraform output -raw sync_command)
aws bedrock-agent get-ingestion-job --knowledge-base-id <kb> --data-source-id <ds> --ingestion-job-id <job>
aws bedrock-agent get-data-source --knowledge-base-id <kb> --data-source-id <ds>
aws s3 ls s3://<docs_bucket>/ --recursive
aws s3vectors get-index --vector-bucket-name <vector_bucket> --index-name manuals
aws s3vectors list-vectors --vector-bucket-name <vector_bucket> --index-name manuals --max-results 5
aws bedrock-agent-runtime retrieve --knowledge-base-id <kb> --retrieval-query text="tent warranty"
```

## Hint ladder

<details><summary>Hint 1: start at the agent</summary>

The first error is the agent's own. Which API does the `search_manuals` tool call, and which
action does the role allow? `Retrieve` and `RetrieveAndGenerate` are different IAM actions.
</details>

<details><summary>Hint 2: an empty sync isn't a successful sync</summary>

An ingestion job that finishes `COMPLETE` with `numberOfDocumentsScanned: 0` found nothing to
read. Compare the data source's S3 configuration with where the documents actually are.
</details>

<details><summary>Hint 3: documents fail during indexing</summary>

Read the ingestion job's `failureReasons`. Bedrock writes each chunk's **text** into the vector's
metadata. S3 Vectors limits *filterable* metadata per vector. Which index setting controls this,
and can it be changed in place?
</details>

## Red herrings

- The embedding dimensions (1024) match Titan Text Embeddings V2. Don't change them.
- `cosine` is a fine distance metric.
- The KB's own IAM role (`riverbend-m3-kb-*`) is correct.

## Debrief questions

1. What's the difference between `Retrieve` and `RetrieveAndGenerate`, and why does an agent usually want `Retrieve`?
2. Why did fixing the index force Terraform to replace resources? What does that mean for a production knowledge base?
3. The chunks here are about 1,000 tokens. What would smaller chunks change for retrieval quality, and for the metadata limit?
4. When would you pick OpenSearch Serverless or Aurora pgvector over S3 Vectors?
