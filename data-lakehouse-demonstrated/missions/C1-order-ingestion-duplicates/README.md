# Challenge C1: Orders are counted twice

**Exam objective:** *Troubleshoot order ingestion to eliminate duplicate records*
**Services:** AWS Glue (Spark 3.5, Glue 5.0), Apache Iceberg, Amazon S3, Amazon Athena
**Time:** 25–35 minutes  |  **Deploy:** `./scripts/deploy.sh C1` (after `./scripts/deploy.sh base`)

## Situation

Riverbend's order system exports one JSON Lines file per day to `s3://<raw bucket>/orders/dt=YYYY-MM-DD/`. A Glue job,
[`glue/orders_ingest.py`](glue/orders_ingest.py) (`riverbend-lh-c1-orders-ingest`), loads each day into the Iceberg table
`riverbend_lakehouse.orders` with `MERGE INTO`. Finance reports that order counts and revenue are too high, and that some orders show
the wrong status.

The exports are messy, and the job must cope with all of this:
- the export job sometimes **re-sends lines**, so identical rows appear twice in one file
- an order can change status **several times in one day** (PLACED, then CANCELLED an hour later)
- later files contain **status updates** of earlier orders (PLACED → SHIPPED)
- the export system occasionally **replays an old file**, containing stale versions of orders

Every row carries `order_id` (the business key) and `updated_at` (when that version was produced).

## Run the pipeline

```bash
python3 missions/C1-order-ingestion-duplicates/scenarios/deliver_and_ingest.py   # empties the table, delivers 3 days, runs the job per day
python3 missions/C1-order-ingestion-duplicates/scenarios/check.py
```

## Objectives

1. The job runs successfully for every day.
2. `riverbend_lakehouse.orders` has exactly **one row per order**, holding its **latest** version, however often and in whatever order the versions arrive.
3. Re-running the whole pipeline produces the same result (idempotent).

## Done when

```
PASS  every order is ingested exactly once (600 rows, 600 distinct order_id)
PASS  each order carries its latest status (replays and same-day changes handled)
PASS  status totals match the source of truth (PLACED 480, SHIPPED 100, CANCELLED 20)
PASS  non-cancelled revenue is 110120.00
```

## Useful commands

```bash
aws glue get-job-runs --job-name riverbend-lh-c1-orders-ingest --max-items 3 --query 'JobRuns[].[JobRunState,ErrorMessage]'
aws glue get-job --job-name riverbend-lh-c1-orders-ingest --query 'Job.DefaultArguments'
# Athena (workgroup riverbend-lh):
#   SELECT order_id, count(*) FROM riverbend_lakehouse.orders GROUP BY 1 HAVING count(*) > 1 LIMIT 10;
#   SELECT * FROM riverbend_lakehouse."orders$snapshots";      -- Iceberg metadata tables
#   SELECT * FROM riverbend_lakehouse.orders FOR TIMESTAMP AS OF (current_timestamp - interval '10' minute) LIMIT 10;
```

<details><summary>Hint 1</summary>If the job fails before reading any data, look at how Glue loads table-format libraries. Which job parameter does that?</details>
<details><summary>Hint 2</summary>What identifies "the same order" for a MERGE? What happens to a status update whose <code>updated_at</code> differs from the stored row's?</details>
<details><summary>Hint 3</summary>Within one batch, which version of an order should survive? Across batches, what stops a replayed old version from winning?</details>
