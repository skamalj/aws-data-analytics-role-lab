# Challenge C1 solution: Orders are counted twice

```bash
patch -p1 < solutions/C1-order-ingestion-duplicates/fix.patch
./scripts/deploy.sh C1
python3 missions/C1-order-ingestion-duplicates/scenarios/deliver_and_ingest.py
python3 missions/C1-order-ingestion-duplicates/scenarios/check.py
```

Verified locally with Spark 3.5.4 + Iceberg 1.7.1 (the Glue 5.0 versions) on the same data:

| Version | Rows | Distinct orders | Stale statuses |
|---|---|---|---|
| Broken (after fix 1) | 700 | 600 | 120 |
| Fixes 1–3, no recency guard | 600 | 600 | 50 (the replay overwrote SHIPPED with PLACED) |
| All fixes | 600 | 600 | 0 |

| # | Fault | Fix |
|---|---|---|
| 1 | `datalake_formats = ""`, so the job has no Iceberg runtime. `MERGE INTO` / `glue_catalog` fail (`IcebergSparkSessionExtensions` class not found, or the table isn't found) | `--datalake-formats iceberg` (the module default) |
| 2 | `MERGE … ON t.order_id = s.order_id AND t.updated_at = s.updated_at`. Every new *version* of an order has a new `updated_at`, so it never matches and is **inserted** as a second row | Join on the **business key only**: `ON t.order_id = s.order_id` |
| 3 | In-batch dedup ordered `updated_at ASC`, so it keeps the **oldest** version (the 20 orders cancelled later that day stay PLACED) | `ORDER BY updated_at DESC`, `row_number() = 1`. This also removes exact duplicates, which MERGE requires: a target row may be matched by only one source row |
| 4 | `WHEN MATCHED THEN UPDATE SET *` lets a **replayed** old file overwrite newer data | `WHEN MATCHED AND s.updated_at > t.updated_at THEN UPDATE SET *`. Out-of-order and replayed data can now never move an order backwards |

**Why this is idempotent:** re-running any day finds every order already present with the same or a newer `updated_at`, so nothing changes.
**Exam tip:** "duplicates in an Iceberg table" almost always means the wrong MERGE key, missing in-batch dedup, or `append()` where `MERGE` was needed.
