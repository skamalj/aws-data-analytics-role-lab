# Lab 08: Daily Batch Extraction

## Scenario

Riverbend's order-management system runs on **Amazon Aurora PostgreSQL** in
a private VPC with no internet access. Analysts are currently allowed to query
production directly, and it slows down checkout. You must build a **nightly
batch extraction** that copies each day's new and changed orders into the data
lake, **without** opening the database to the internet and **without**
re-copying the whole table every night. The pipeline needs orchestration,
safe re-runs (backfills) and notifications.

## What the starting environment gives you

`./scripts/deploy.sh 08-daily-batch-extraction` creates (takes ~10 minutes):

| Resource | Notes |
|---|---|
| VPC with 2 private subnets | No internet gateway, no NAT |
| Aurora PostgreSQL Serverless v2 `cq-da-08-orders` | Database `riverbend`, table `sales.orders` (5,000 orders Jan–Jun 2024, with an `updated_at` column). **Data API enabled.** Master password in Secrets Manager (`DbSecretArn`) |
| Security groups | `GlueSecurityGroupId` (self-referencing). The database SG accepts 5432 only from it |
| VPC endpoints | S3 (gateway), Secrets Manager and Glue (interface) |
| Buckets | `ExtractBucket` (your output), `ScriptsBucket` |
| Glue database `riverbend_extracts`, Athena workgroup `cq-da-08` | |
| IAM roles | `cq-da-08-glue-job-role` (can read the DB secret), `cq-da-08-sfn-role` (Step Functions + Scheduler) |
| SNS topic `cq-da-08-batch-notifications` | Subscribe your e-mail address to it |

Scenario driver: `python3 labs/08-daily-batch-extraction/infra/new_day.py --date 2024-07-01`
simulates one business day (inserts new orders and updates older ones to `RETURNED`).

> **Cost:** roughly $2–3/day while the stack exists (Aurora at its 0.5 ACU minimum plus the interface endpoints). Destroy it when you've finished.

## Your tasks

1. **Explore the source.** Use the RDS console's **Query editor** (Data API +
   the secret) to look at `sales.orders`. Which column tells you that a row changed?
2. **Create a Glue JDBC connection** `cq-da-08-aurora` that uses the secret,
   private subnet A and the Glue security group. **Test the connection.**
3. **Write a Glue job** `cq-da-08-daily-extract` with parameters `--run_date YYYY-MM-DD` and `--mode full|incremental`:
   - `full`: every row with `updated_at` before the end of `run_date`
   - `incremental`: only rows whose `updated_at` is on `run_date`
   - the filter must run **in PostgreSQL**, not in Spark
   - output is Parquet at `s3://<ExtractBucket>/orders_changes/extract_date=<run_date>/`, and
     re-running the same date must **replace** that partition, not duplicate it
4. **Catalog** the output as `riverbend_extracts.orders_changes`, so that new
   `extract_date`s are queryable without a crawler.
5. **Orchestrate with Step Functions.** State machine `cq-da-08-daily-batch`:
   run the job and wait for it → count the extracted rows with Athena →
   publish a success message (date, mode, row count) to SNS. On any failure,
   publish a failure message and fail the execution. If the input has no
   `run_date`, use **yesterday**.
6. **Run the history:**
   - full load with `{"run_date":"2024-06-30","mode":"full"}`
   - `new_day.py --date 2024-07-01`, then run with `{"run_date":"2024-07-01"}`
   - `new_day.py --date 2024-07-02`, then run with `{"run_date":"2024-07-02"}`
   - run 2024-07-01 **again** and show nothing changed
7. Create an Athena view `riverbend_extracts.orders_current` that shows the **latest** version of each order.
8. **Schedule** the state machine daily at 01:30 UTC with EventBridge Scheduler.

## How you know you're done

Counts match [`expected-results.md`](../../solutions/08-daily-batch-extraction/expected-results.md).

## Hints

<details><summary>Glue cannot reach the database / times out</summary>Check the self-referencing rule on the Glue SG, that the DB SG allows the Glue SG, and that the S3 endpoint is on the subnet's route table.</details>
<details><summary>Push-down</summary>Spark's JDBC source has a <code>query</code> option, and Glue's has <code>sampleQuery</code>. Either one sends your SQL to the database.</details>
<details><summary>Yesterday in Step Functions</summary>JSONata: <code>$fromMillis($toMillis($now()) - 86400000, '[Y0001]-[M01]-[D01]')</code>.</details>

## DIY challenge

- Add a *Map* state so one execution can backfill a list of dates.
- Load each extract into Redshift (Lab 07) with a `COPY`, and `MERGE` into the fact table.

## Cleanup

```bash
./solutions/08-daily-batch-extraction/cleanup.sh
./scripts/destroy.sh 08-daily-batch-extraction
```
