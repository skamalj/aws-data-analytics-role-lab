# Mission D8: Product search is too slow for a conversation

**Exam objective:** *Optimize the agent's product search queries*
**Skills:** reading `EXPLAIN` plans, trigram (`pg_trgm`) GIN indexes for `ILIKE '%…%'`, composite B-tree indexes, HNSW for similarity, pushing filters, sorting and limits into SQL, the RDS Data API's 1 MB response limit, **CloudWatch** latency metrics (Embedded Metric Format) and dashboards
**Time:** 45 minutes  |  **Needs:** `./scripts/deploy.sh base`, then `./scripts/deploy.sh D8` (the first deploy loads 200,000 products, which takes a minute or two)

## Situation

Riverbend's catalog grew to **200,000 products**, and Trail Desk's product questions now feel broken. Answers take
seconds, or the agent says the search failed. The agent waits on its tools before it can say anything, so the
product team set an SLA: **every product tool must answer in under 150 ms (p95)**, measured by the tool itself and published to CloudWatch.

| Tool (one Lambda, [`lambdas/product_search.py`](lambdas/product_search.py)) | Used for |
|---|---|
| `search_products(query, category?, max_price?, limit?)` | "waterproof jackets under 150" |
| `browse_category(category, max_price)` | "cheapest footwear" |
| `similar_products(product_id)` | "show me things like X012345" (64-d product embeddings, cosine) |

The catalog launched with **no secondary indexes** ([`db/indexes.sql`](db/indexes.sql)).

## Symptoms

```bash
python3 missions/D8-product-search-optimization/scenarios/check.py
```

Also open the CloudWatch dashboard from `terraform -chdir=missions/D8-product-search-optimization/terraform output dashboard`.

## Objectives

1. `search_products` returns correct, filtered results for common terms (for example "waterproof"), without errors.
2. Tools return only the columns the agent needs, and never more than 20 rows.
3. Each tool's query shape is served by an index: trigram for text search, `(category, price)` for browsing, HNSW for similarity.
4. p95 latency under 150 ms for every tool. Results must stay the same.

## Done when

`check.py` reports all checks as PASS, and the dashboard shows all three tools below the SLA line.

## Investigation toolkit

```bash
aws logs tail /aws/lambda/riverbend-d8-product-tools --since 10m        # one EMF line per call: Tool, QueryMs, error
python3 common/dbsql.py --sql "EXPLAIN (ANALYZE, BUFFERS) SELECT product_id FROM catalog.products WHERE name ILIKE '%kestrel storm jacket%' ORDER BY rating DESC LIMIT 10"
python3 common/dbsql.py --sql "SELECT indexname, indexdef FROM pg_indexes WHERE schemaname = 'catalog'"
python3 common/dbsql.py --sql "SELECT count(*) FROM catalog.products WHERE description ILIKE '%waterproof%'"
python3 common/dbsql.py --sql "SELECT pg_size_pretty(pg_total_relation_size('catalog.products'))"
```

Performance Insights / CloudWatch Database Insights on the cluster show the top SQL by load, if you've enabled them.

## Hint ladder

<details><summary>Hint 1: "waterproof" fails</summary>How many rows match, and how much does <code>SELECT *</code> return for each one, including the embedding? The Data API returns at most 1 MB per call. Where do the category, price, stock filters and the <code>limit</code> get applied today?</details>
<details><summary>Hint 2: leading wildcards</summary>A B-tree index can't help <code>ILIKE '%term%'</code>. The <code>pg_trgm</code> extension provides <code>gin_trgm_ops</code>. An <code>OR</code> across two columns needs an index on each one to get a <code>BitmapOr</code>.</details>
<details><summary>Hint 3: the other two tools</summary>Equality first, then range or sort: which column order for a composite index? For similarity search, which index type, and which operator class for <code>&lt;=&gt;</code>?</details>

## Debrief questions

1. Why did fixing the SQL (pushing filters down and adding `LIMIT`) matter as much as the indexes?
2. What does a trigram index cost: in size, in write speed, and for very short search terms?
3. When would you prefer PostgreSQL full-text search (`tsvector`) or semantic (embedding) search over trigrams for product search?
4. How would you alert on SLA breaches in production?
