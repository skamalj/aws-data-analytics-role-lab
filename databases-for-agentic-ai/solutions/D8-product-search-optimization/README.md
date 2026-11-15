# Mission D8 solution: Product search is too slow for a conversation

```bash
patch -p1 < solutions/D8-product-search-optimization/fix.patch
./scripts/deploy.sh D8        # applies indexes.sql (index builds take ~1 min) and the new Lambda code
python3 missions/D8-product-search-optimization/scenarios/check.py
```

## Fault 1: `search_products` filters in Python, after fetching everything

| | |
|---|---|
| Symptom | `"waterproof"` fails with *Database returned more than the allowed response size limit*. Selective terms are slow |
| Root cause | `SELECT *`, including the 64-d embedding and long descriptions, for **every** match (33,333 rows for "waterproof"). Category, price, stock, sorting and the limit were all applied in Python afterwards |
| Fix | Build one SQL statement: select only `product_id, name, category, price, rating`, put every filter in `WHERE`, then `ORDER BY rating DESC LIMIT :lim` (max 20). Parameters are typed (`longValue` for the limit) |

## Fault 2: no index can serve `ILIKE '%term%'`

| | |
|---|---|
| Symptom | `Seq Scan on products` for every search |
| Fix | `CREATE EXTENSION pg_trgm`, then GIN `gin_trgm_ops` indexes on **both** `name` and `description`. The plan becomes `BitmapOr` over two `Bitmap Index Scan`s |

## Fault 3: no indexes for browsing or similarity

| Tool | Fix | Plan after |
|---|---|---|
| `browse_category` | `CREATE INDEX … (category, price)`: equality column first, then the range/sort column | `Index Scan using products_category_price`, with no sort and early stop at `LIMIT 20` |
| `similar_products` | `CREATE INDEX … USING hnsw (embedding vector_cosine_ops)` | `Index Scan using products_embedding_hnsw … Order By (embedding <=> $0)` |

Measured on a local PostgreSQL 16 with the same 200k rows: text search 58 → 17 ms, browse 24 → 0.2 ms, similar 35 → 1 ms.
On Aurora Serverless at low capacity, and with the Data API round-trip added, the "before" numbers are several times worse.

## Debrief answers

1. Without pushdown the database must read, serialise and ship every matching row, and the Lambda must parse them. No index fixes moving 30 MB
   of data. Indexes only help once the query asks for little.
2. GIN trigram indexes are large (often comparable to the column data), slow down inserts and updates, and are weak for terms under 3 characters
   (which is why the fixed tool rejects them).
3. Full-text search for word-based relevance ranking, stemming and languages. Semantic search for meaning ("something warm for a winter hike").
   Many stores combine them: hybrid ranking.
4. A CloudWatch alarm on `Riverbend/ProductSearch QueryMs` p95 > 150 for 3 of 5 minutes, sent to the on-call team's SNS topic, plus Database
   Insights to find the offending SQL.
