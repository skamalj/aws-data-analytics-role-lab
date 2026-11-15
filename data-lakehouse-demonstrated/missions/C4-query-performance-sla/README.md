# Challenge C4: The dashboard is too slow

**Exam objective:** *Optimize analytics query performance to sub-5-second SLA*
**Services:** Amazon Athena, Apache Iceberg (file layout, table properties, snapshots), AWS Glue (Spark maintenance)
**Time:** 30–40 minutes  |  **Deploy:** `./scripts/deploy.sh C4` (the post-deploy step loads 20,000,000 sales rows, which takes ~5 minutes once)

## Situation

`riverbend_lakehouse.sales` (Iceberg, partitioned by `day(sold_at)`) was filled by a legacy streaming loader. The finance dashboard runs
three queries ([`sql/dashboard.sql`](sql/dashboard.sql)) and the business has set an **SLA of under 5 seconds per query**. Today they take
far longer.

For Iceberg maintenance that Athena can't do, the team has a Spark maintenance job that runs your
[`sql/maintenance.sql`](sql/maintenance.sql) (`scenarios/run_maintenance.py`). Athena can also run `OPTIMIZE … REWRITE DATA USING BIN_PACK`
and `VACUUM` on Iceberg tables.

## Check

```bash
python3 missions/C4-query-performance-sla/scenarios/check.py
```

## Objectives

1. Each dashboard query returns the **same results** in **under 5 seconds** of Athena engine time.
2. Date-filtered queries read only the partitions they need.
3. The table stays healthy: future writes don't recreate the problem, and history doesn't grow forever.

## Done when

`check.py` reports all checks passed: compaction, snapshots, and for each of Q1–Q3 correctness and under 5 s (plus pruning for Q1 and Q3).

## Useful commands

```sql
SELECT count(*), avg(file_size_in_bytes), min(file_size_in_bytes) FROM riverbend_lakehouse."sales$files";
SELECT partition, count(*) AS files FROM riverbend_lakehouse."sales$files" GROUP BY 1 ORDER BY 2 DESC LIMIT 5;
SELECT * FROM riverbend_lakehouse."sales$snapshots";
SHOW TBLPROPERTIES riverbend_lakehouse.sales;
EXPLAIN ANALYZE <query>;      -- Athena: where does the time go?
```

<details><summary>Hint 1</summary>How many data files, and how big? What does every query have to do for each file? What does the table tell every writer the file size should be, compaction included?</details>
<details><summary>Hint 2</summary>Iceberg partition pruning works on predicates over the <b>source column</b> (<code>sold_at</code>). What can it do with <code>date_format(sold_at, …) = '…'</code>?</details>
<details><summary>Hint 3</summary>After compacting, the old small files are still referenced by old snapshots. Which maintenance operation removes them from planning and storage?</details>
