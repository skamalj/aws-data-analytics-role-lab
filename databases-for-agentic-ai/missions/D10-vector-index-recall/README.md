# Mission D10: Fast answers, wrong answers

**Based on:** *Leverage pgvector and Amazon Aurora PostgreSQL for natural language processing, chatbots and sentiment analysis* (AWS Database Blog), which compares IVFFlat and HNSW
**Skills:** IVFFlat vs HNSW, `lists`/`probes`, `m`/`ef_construction`/`ef_search`, measuring **recall** against exact search, session settings per database role
**Time:** 35–45 minutes  |  **Needs:** `./scripts/deploy.sh base`, then `./scripts/deploy.sh D10` (SQL only, about 1 minute)

## Situation

Trail Desk's "similar reviews" feature uses approximate nearest-neighbour (ANN) indexes. The team is evaluating
two candidates, each over the same 20,000 review embeddings ([`db/setup.sql`](db/setup.sql)):

| Table | Index | Used for |
|---|---|---|
| `vectors.reviews_ivf` | IVFFlat (`vector_cosine_ops`) | the agent's top-10 similar reviews |
| `vectors.reviews_hnsw` | HNSW (`vector_cosine_ops`) | exporting the **top 100** candidates to a re-ranker |

Both are fast. Product managers say the results "look random", and the re-ranker complains it gets too few candidates.
ANN indexes trade accuracy for speed, so the team needs to **measure** that trade-off rather than guess.

## Symptoms

```bash
python3 missions/D10-vector-index-recall/scenarios/check.py
```

## Objectives

1. IVFFlat recall@10 ≥ 0.95 for the agent's queries (run as `trail_desk_app`).
2. The HNSW export returns **100** rows with recall@100 ≥ 0.95.
3. Both still use their index, in under 25 ms.
4. Fix it in `db/setup.sql` (index build and the application role's settings). Don't change the queries.

## Done when

`check.py` reports 5/5 checks passed.

## Investigation toolkit

```bash
python3 common/dbsql.py --sql "SELECT indexname, indexdef FROM pg_indexes WHERE schemaname = 'vectors'"
python3 common/dbsql.py --as app --sql "SELECT current_setting('ivfflat.probes'), current_setting('hnsw.ef_search')"
python3 common/dbsql.py --sql "SELECT rolname, rolconfig FROM pg_roles WHERE rolname = 'trail_desk_app'"
python3 common/dbsql.py --as app --sql "EXPLAIN ANALYZE SELECT id FROM vectors.reviews_ivf ORDER BY embedding <=> (SELECT embedding FROM vectors.reviews_ivf WHERE id = 42) LIMIT 10"
```

The deploy output shows any PostgreSQL warnings from building the indexes. Read them.

## Hint ladder

<details><summary>Hint 1: IVFFlat</summary>IVFFlat runs k-means when the index is <b>built</b>, and assigns rows to the nearest centroid. What were the centroids based on here? How many lists make sense for 20,000 rows, and how many of them does a query search by default?</details>
<details><summary>Hint 2: HNSW returns 40 rows</summary>An HNSW index scan keeps a candidate list of size <code>hnsw.ef_search</code> (default 40). What happens with <code>LIMIT 100</code>?</details>
<details><summary>Hint 3: where do settings live?</summary><code>SET</code> applies to one session, and every Data API call can be a different session. <code>ALTER ROLE … SET …</code> applies to every new session of that role.</details>

## Debrief questions

1. Why is "the query uses the index and is fast" not proof that vector search works?
2. When would you choose IVFFlat over HNSW?
3. How does `hnsw.ef_search` interact with filtered queries (`WHERE tenant_id = …`)? Mission D12 runs into this.
4. How would you keep recall high as the table grows from 20,000 to 20 million rows?
