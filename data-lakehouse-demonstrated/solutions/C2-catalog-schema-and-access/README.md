# Challenge C2 solution: The new supplier feed loses data, and catalog queries scan everything

```bash
patch -p1 < solutions/C2-catalog-schema-and-access/fix.patch    # writes sql/maintenance.sql
python3 missions/C2-catalog-schema-and-access/scenarios/run_maintenance.py
python3 missions/C2-catalog-schema-and-access/scenarios/deliver_feed.py
python3 missions/C2-catalog-schema-and-access/scenarios/check.py
```

```sql
-- sql/maintenance.sql (Spark SQL)
ALTER TABLE glue_catalog.riverbend_lakehouse.products ADD COLUMN brand string;
ALTER TABLE glue_catalog.riverbend_lakehouse.products ALTER COLUMN price TYPE double;
ALTER TABLE glue_catalog.riverbend_lakehouse.products ALTER COLUMN stock TYPE bigint;
ALTER TABLE glue_catalog.riverbend_lakehouse.products ADD PARTITION FIELD category;
ALTER TABLE glue_catalog.riverbend_lakehouse.products DROP PARTITION FIELD bucket(16, product_id);
CALL glue_catalog.system.rewrite_data_files(table => 'riverbend_lakehouse.products', options => map('rewrite-all', 'true'));
```

Verified locally with Spark 3.5.4 + Iceberg 1.7.1. The broken merge reports success, but `brand` is dropped and 20.95 is stored as
20.950000762939453 (float). After the fix, all 2,000 feed rows have a brand, prices are exact doubles, and the files are rewritten into
6 `category` partitions (one partition spec left).

| # | Fault | Fix |
|---|---|---|
| 1 | Feed has `brand`, the table doesn't. `MERGE … SET * / INSERT *` uses the **target** schema, so the extra column is silently dropped | `ADD COLUMN brand string`. This is metadata only: old files simply have no value for it |
| 2 | Feed prices are doubles, the column is `float`, so they're silently narrowed (`20.95` becomes `20.950000762939453`) | `ALTER COLUMN price TYPE double`, an allowed Iceberg **promotion**, with no rewrite. Also `stock int → bigint`, since JSON integers arrive as long. Narrowing or changing type kind (for example `string → int`) isn't allowed |
| 3 | Partitioned by `bucket(16, product_id)`, but queries filter on `category`, so every file has every category and nothing is pruned | **Partition evolution**: add `category`, drop the bucket field, then `rewrite_data_files` (`rewrite-all`) so existing data moves into the new spec. Without the rewrite only *new* data would be pruned |

Athena can add, rename and drop columns and promote types on Iceberg tables, but partition evolution and `rewrite_data_files` need Spark (or a CTAS into a new table).
Hidden partitioning means queries don't change: `WHERE category = 'Tents'` now prunes automatically.
