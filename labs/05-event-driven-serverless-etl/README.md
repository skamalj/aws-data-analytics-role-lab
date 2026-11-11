# Lab 05: Event-Driven Serverless ETL

## Scenario

The order system now drops one CSV file per day into `incoming/orders/` in the
landing bucket, at unpredictable times. Today an analyst runs a script by hand
the next morning. Riverbend wants each file **processed automatically within
minutes of landing**, with no servers to manage:

- Valid orders are cleaned and appended to a curated Parquet table, partitioned by order date.
- `CANCELLED` orders are dropped.
- Lines the POS gateway sent twice are de-duplicated.
- Corrupt rows must **not** break the pipeline. Park them in a quarantine area for review.
- If the job itself fails, the data team gets an alert.

## What the starting environment gives you

`./scripts/deploy.sh 05-event-driven-serverless-etl` creates:

| Resource | Output | Notes |
|---|---|---|
| Landing bucket | `LandingBucket` | **EventBridge notifications already enabled** |
| Curated bucket | `CuratedBucket` | Write `orders/` and `quarantine/` here |
| Scripts bucket | `ScriptsBucket` | Put your Glue script here |
| Glue database `riverbend_curated` | `GlueDatabase` | |
| IAM role for Glue jobs | `GlueJobRoleArn` | Reads landing + scripts, writes curated |
| IAM role for Lambda | `TriggerLambdaRoleArn` | Can start Glue jobs named `cq-da-05-*` and write logs |
| Athena workgroup `cq-da-05` | | |

A scenario driver uploads files for you:

```bash
python3 labs/05-event-driven-serverless-etl/infra/drop_files.py        # July 1-3 (day 2 contains duplicate lines)
python3 labs/05-event-driven-serverless-etl/infra/drop_files.py --bad  # July 4, with 5 corrupt lines
```

File layout: CSV with header, the same 12 columns as previous labs
(`order_id, order_ts, …, region, status`).

## Your tasks

1. **Write a Glue (Spark) job** `cq-da-05-orders-etl` that takes the bucket
   and key of **one** file as job arguments and:
   - validates rows: `order_id` present, `order_ts` a valid timestamp, `quantity > 0`,
     `total_amount >= 0`, `region` one of NA/EU/APAC/LATAM, `status` one of COMPLETED/RETURNED/CANCELLED
   - writes invalid rows as JSON to `s3://<CuratedBucket>/quarantine/`
   - drops `CANCELLED` orders and duplicate `order_id`s
   - adds `source_file` and `ingest_ts` columns
   - appends Parquet to `s3://<CuratedBucket>/orders/`, partitioned as `order_date=YYYY-MM-DD`
2. **Trigger it from events.** When an object matching `incoming/orders/*.csv`
   is created in the landing bucket, an **EventBridge rule** invokes a **Lambda**
   function `cq-da-05-start-etl`, which starts the job for that file. Several
   files arriving at once must all be processed.
3. **Catalog the output** so that `riverbend_curated.orders` is queryable in
   Athena, and new dates appear without running a crawler.
   Also create `riverbend_curated.orders_quarantine`.
4. **Alert on failure.** A Glue job run that ends `FAILED`, `TIMEOUT` or `ERROR`
   publishes to an SNS topic `cq-da-05-etl-alerts`. Subscribe your e-mail address.
5. **Test it:** run `drop_files.py`, then `drop_files.py --bad`, and check the
   results in Athena. Then prove the alert works, for example by temporarily
   pointing the job at a script path that doesn't exist.

## How you know you're done

Numbers match [`expected-results.md`](../../solutions/05-event-driven-serverless-etl/expected-results.md):
1,171 curated rows across 4 dates, 5 quarantined rows, and 4 successful job runs.

## Hints

<details><summary>Getting the file name into the job</summary>The EventBridge S3 event has <code>detail.bucket.name</code> and <code>detail.object.key</code>. Pass them to <code>StartJobRun</code> as <code>Arguments</code> and read them with <code>getResolvedOptions</code>.</details>
<details><summary>Corrupt rows in Spark</summary>Read with an explicit schema, <code>mode=PERMISSIVE</code> and <code>columnNameOfCorruptRecord</code>. Cache the DataFrame before you filter on the corrupt column.</details>
<details><summary>Concurrency</summary>Look at the job's <i>Maximum concurrency</i> setting.</details>

## DIY challenge

- Make the pipeline idempotent across files (see the end of the solution README).
- Replace the Lambda with a Step Functions state machine that runs the job with `.sync`, then runs a data-quality check.

## Cleanup

```bash
./solutions/05-event-driven-serverless-etl/cleanup.sh   # if you used the reference solution stack
./scripts/destroy.sh 05-event-driven-serverless-etl
```

Delete by hand anything you built yourself in the console: the Glue job, Lambda, EventBridge rules, SNS topic and Glue tables.

**Cost:** about $0.02–0.05 per Glue job run (2 × G.1X workers, 1-minute minimum). Everything else is in the free tier.
