# Mission D13: Partner A gets partner B's answers

**Based on:** *Multi-tenant vector search with Amazon Aurora PostgreSQL and Amazon Bedrock Knowledge Bases* (AWS Database Blog), and the SimuLearn *Create Trustworthy LLMs with a Vector Database* objectives "use metadata filtering to retrieve relevant results" and "troubleshoot data ingestion and metadata formatting"
**Skills:** Knowledge Base metadata sidecars (`<file>.metadata.json`, `metadataAttributes`), `custom_metadata` on Aurora, `Retrieve` filters (`equals`, `andAll`), tenant identity from trusted context vs model arguments
**Time:** 45 minutes  |  **Needs:** `./scripts/deploy.sh base`, then `./scripts/deploy.sh D13`, then the sync:
`$(terraform -chdir=missions/D13-multi-tenant-kb-metadata/terraform output -raw sync_command)`

## Situation

Three partner shops resell Trail Desk: **north-trail**, **coastline** and **peak-gear**. They share **one** Bedrock
Knowledge Base on Aurora pgvector (`bedrock_kb.d13_chunks`), which is cheaper and simpler than one per partner. Each partner's
policies live under `docs/<tenant>/` with a metadata **sidecar** per document:

```json
// docs/north-trail/returns.md.metadata.json
{ "metadataAttributes": { "tenant_id": "north-trail", "audience": "customer", "doc_type": "returns" } }
```

The search tool [`lambdas/partner_search.py`](lambdas/partner_search.py) receives the partner from the **authenticated
request context** (`event.context.tenant_id`) and the customer's question from the model (`event.args.query`). It must filter every
`Retrieve` call to that tenant.

## Symptoms

```bash
python3 missions/D13-multi-tenant-kb-metadata/scenarios/check.py
aws bedrock-agent get-ingestion-job --knowledge-base-id <kb> --data-source-id <ds> --ingestion-job-id <job> --query 'ingestionJob.[statistics,failureReasons]'
```

Some partners get no answers, the sync statistics look odd, and one partner can see another's documents.

## Objectives

1. All 6 partner documents are indexed with their metadata (0 failures), and every chunk carries a `tenant_id`.
2. Each partner's search answers only from its own documents.
3. The tenant can't be changed by anything the model sends.
4. Keep one shared knowledge base. Fix the sidecars and the tool, then re-sync.

## Done when

`check.py` reports 6/6 checks passed.

## Investigation toolkit

```bash
find missions/D13-multi-tenant-kb-metadata/docs -type f | sort
python3 common/dbsql.py --sql "SELECT custom_metadata, left(chunks, 60) FROM bedrock_kb.d13_chunks"
python3 common/dbsql.py --sql "SELECT metadata->>'x-amz-bedrock-kb-source-uri' AS source, custom_metadata FROM bedrock_kb.d13_chunks"
aws bedrock-agent-runtime retrieve --knowledge-base-id <kb> --retrieval-query text="return window" \
  --retrieval-configuration '{"vectorSearchConfiguration":{"filter":{"equals":{"key":"tenant_id","value":"peak-gear"}}}}'
```

## Hint ladder

<details><summary>Hint 1: coastline never answers</summary>The Knowledge Base pairs a document with its sidecar <b>by file name</b>. For <code>returns.md</code>, what must the sidecar be called? What happens to a JSON file that isn't recognised as a sidecar?</details>
<details><summary>Hint 2: one peak-gear document has no tenant</summary>Compare the structure of its sidecar with the others. Read the sync's <code>failureReasons</code>.</details>
<details><summary>Hint 3: the tool</summary>Which metadata key does the filter use, compared with the sidecars? And which input wins when both the context and the model's arguments contain a tenant?</details>

## Debrief questions

1. Which metadata should be **filterable**, and why is `tenant_id` a filter rather than a separate knowledge base per tenant?
2. Why is metadata filtering at retrieval time not enough on its own for high-risk data? What else would you add?
3. How would you validate sidecars before they reach S3?
4. How does this compare with D12's row-level security approach?
