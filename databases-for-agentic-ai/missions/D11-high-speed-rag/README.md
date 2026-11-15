# Mission D11: Fast RAG that isn't fast

**Based on:** [Guidance for High-Speed RAG Chatbots on AWS](https://docs.aws.amazon.com/solutions/high-speed-rag-chatbots-on-aws/): Aurora PostgreSQL + pgvector with HNSW, Titan embeddings reduced to 512 dimensions (~99 % of the 1024-d retrieval accuracy)
**Skills:** embedding dimension reduction done consistently, query-embedding caching in DynamoDB (deterministic keys, TTL), Lambda cold vs warm starts and client reuse, latency budgets with CloudWatch EMF metrics
**Time:** 40 minutes  |  **Needs:** `./scripts/deploy.sh base`, then `./scripts/deploy.sh D11`

## Situation

Voice customers expect Trail Desk to answer within a breath. The team built a latency-optimised retrieval tool,
[`lambdas/fast_answer.py`](lambdas/fast_answer.py), following AWS's high-speed RAG guidance:

- move from 1024-d to **512-d** Titan V2 embeddings: half the storage and a smaller HNSW graph, for nearly the same accuracy
- **cache query embeddings** in DynamoDB, so repeated questions ("where's my order", "returns policy") skip Bedrock
- report a **latency breakdown** for every call (`client_init_ms`, `embed_ms`, `search_ms`, `total_ms`, `cache_hit`) to CloudWatch (`Riverbend/FastRag`)

The passages are stored by `post_deploy.py`, which embeds `docs/*.md` at whatever dimension
[`db/schema.sql`](db/schema.sql) declares.

## Symptoms

```bash
python3 missions/D11-high-speed-rag/scenarios/check.py
aws lambda invoke --function-name riverbend-d11-fast-answer --payload '{"question":"returns policy for used stoves"}' \
  --cli-binary-format raw-in-base64-out /dev/stdout
```

## Objectives

1. 512 dimensions **everywhere**: stored vectors, column type, index and query embeddings.
2. A repeated question is served from the cache.
3. Warm invocations don't pay client set-up time again.
4. Cached answers take under 150 ms end to end (p95), with the right document first.

## Done when

`check.py` reports 6/6 checks passed, and the `Riverbend/FastRag` metrics show `embed_ms ≈ 0` on cache hits.

## Investigation toolkit

```bash
aws logs tail /aws/lambda/riverbend-d11-fast-answer --since 10m     # one EMF line per call with the timings
aws dynamodb scan --table-name riverbend-d11-embedding-cache --select COUNT
python3 common/dbsql.py --sql "SELECT format_type(atttypid, atttypmod) FROM pg_attribute WHERE attrelid='knowledge.d11_chunks'::regclass AND attname='embedding'"
python3 common/dbsql.py --sql "SELECT vector_dims(embedding), count(*) FROM knowledge.d11_chunks GROUP BY 1"
```

The first call after the cluster has auto-paused waits for Aurora to resume. `check.py` warms up before it measures.

## Hint ladder

<details><summary>Hint 1: the error</summary>"different vector dimensions": who decided on 512, and did the stored data follow? What has to happen to existing vectors when the dimension changes?</details>
<details><summary>Hint 2: the cache never hits</summary>Print the cache key for the same question twice.</details>
<details><summary>Hint 3: client_init_ms on every call</summary>Code at module level runs once per execution environment. Code inside the handler runs on every invocation.</details>

## Debrief questions

1. What exactly do you gain from 512-d vectors, and how would you verify the accuracy claim on *your* data?
2. What should a query-embedding cache key contain, and when must the cache be invalidated?
3. Name three other latency levers for this path (think provisioned concurrency, Data API vs a direct connection, LIMIT/`ef_search`).
4. What's the difference between caching *embeddings* and caching *answers*, and what are the risks of each?
