# Mission D11 solution: Fast RAG that isn't fast

```bash
patch -p1 < solutions/D11-high-speed-rag/fix.patch
./scripts/deploy.sh D11            # rebuilds the table at vector(512); post_deploy.py re-embeds at 512
python3 missions/D11-high-speed-rag/scenarios/check.py
```

## Fault 1: only half of the system moved to 512 dimensions

| | |
|---|---|
| Symptom | Every call fails: `different vector dimensions 1024 and 512` |
| Root cause | The Lambda embeds queries at `EMBED_DIMENSIONS = 512`, but the column (and every stored vector and the HNSW index) is still `vector(1024)`. Vectors from different dimension settings can't be compared, not even by truncating them |
| Fix | `vector(512)` in `schema.sql`. The table and index are rebuilt, and `post_deploy.py` re-embeds the documents at 512. Dimension changes are data migrations, not configuration changes |

## Fault 2: the cache key contains a timestamp

| | |
|---|---|
| Symptom | `cache_hit` is always false, and the cache table fills with unique keys |
| Fix | `sha256(model | dims | normalised question)`. Including model and dimensions in the key means a future change can't serve stale vectors. Expiry uses the table's TTL (`expires_at`) |

## Fault 3: clients are created on every invocation

| | |
|---|---|
| Symptom | `client_init_ms` stays tens to hundreds of ms on every call |
| Fix | Create `rds-data`, `bedrock-runtime` and the DynamoDB `Table` at **module level**. They're built once per execution environment, and warm calls reuse them along with their HTTPS connections |

## Debrief answers

1. Half the storage and memory per vector, a smaller and faster HNSW graph, and less data moved per query. Verify it with a recall/quality benchmark
   on your own question set at 1024 vs 512 (as in D10), before migrating.
2. Everything that changes the vector: model id, dimensions, normalisation, and the normalised input text. Invalidate on model or dimension change
   (or include them in the key, as here). TTL bounds staleness.
3. Provisioned concurrency (no cold starts). A direct `psycopg` connection through RDS Proxy instead of the Data API (lower per-query overhead). Smaller `LIMIT`
   and tuned `ef_search`. Keeping Aurora at ≥ 0.5 ACU (no resume pauses). Memory/CPU sizing of the Lambda. Response streaming.
4. Embedding caches are safe: the same input always gives the same vector. Answer caches are much faster, but can serve stale or wrong-customer
   answers. Key them on everything that changes the answer (user, permissions, data version) and keep their TTLs short.
