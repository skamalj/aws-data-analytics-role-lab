# Challenge C2: The new supplier feed loses data, and catalog queries scan everything

**Exam objective:** *Troubleshoot product catalog schema mismatch and query access patterns*
**Services:** AWS Glue (Spark), Apache Iceberg schema and partition evolution, Amazon Athena
**Time:** 25–35 minutes  |  **Deploy:** `./scripts/deploy.sh C2` (loads 60,000 SKUs into `riverbend_lakehouse.products`)

## Situation

`riverbend_lakehouse.products` is an Iceberg table, partitioned by `bucket(16, product_id)` when it was created. A supplier has switched to
**feed v2**, which adds a **`brand`** attribute and sends prices **with cents** (e.g. 20.95). The merge job
[`glue/products_merge.py`](glue/products_merge.py) "succeeds", but the merchandising team says brands are missing and prices are off by fractions
of a cent. Meanwhile analysts complain that "show me Tents" queries are as expensive as reading the whole catalog. Almost all catalog
queries filter on **`category`**.

Athena can't do every Iceberg DDL change. The team runs Spark SQL for that through the maintenance job
[`glue/maintenance.py`](glue/maintenance.py), which executes the statements in [`sql/maintenance.sql`](sql/maintenance.sql).

## Run it

```bash
python3 missions/C2-catalog-schema-and-access/scenarios/deliver_feed.py       # supplier feed v2 -> merge job
python3 missions/C2-catalog-schema-and-access/scenarios/check.py
python3 missions/C2-catalog-schema-and-access/scenarios/run_maintenance.py    # runs YOUR sql/maintenance.sql (Spark SQL)
```

## Objectives

1. Feed v2 lands **without silent data loss**: every attribute is kept, and prices are stored exactly.
2. Existing data is kept, with no table rebuild or reload from the source. Evolve the table in place.
3. Single-category queries read only that category's data.

## Done when

```
PASS  products has the supplier's new column 'brand'
PASS  price is stored as double (no float rounding)
PASS  all 61,000 SKUs present and the 2,000 feed rows carry a brand
PASS  feed price 20.95 is stored exactly
PASS  a single-category query reads < 30% of what a full scan reads (partition pruning)
```

(After evolving the table, run `deliver_feed.py` again so the feed is re-merged into the new schema.)

## Useful commands

```sql
-- Athena, workgroup riverbend-lh
DESCRIBE riverbend_lakehouse.products;
SELECT * FROM riverbend_lakehouse."products$partitions" LIMIT 5;
SELECT partition, count(*) AS files, sum(file_size_in_bytes) AS bytes FROM riverbend_lakehouse."products$files" GROUP BY 1;
SELECT product_id, price, brand FROM riverbend_lakehouse.products WHERE product_id = 'SKU000001';
```

<details><summary>Hint 1</summary>Spark's <code>MERGE … UPDATE SET * / INSERT *</code> works on the <b>target</b> table's columns. What happens to a source column the target doesn't have? What does writing a <code>double</code> into a <code>float</code> column do?</details>
<details><summary>Hint 2</summary>Which Iceberg type changes are safe metadata-only promotions (<code>int → bigint</code>, <code>float → double</code>, widening <code>decimal</code>)? Iceberg can also add columns in place.</details>
<details><summary>Hint 3</summary>Iceberg partitioning is a spec that can evolve (<code>ADD/DROP PARTITION FIELD</code>), but only new writes use the new spec. How do you move existing data into it?</details>
