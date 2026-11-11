# Lab 05 solution: Event-Driven Serverless ETL

Files:
- [`etl_orders.py`](etl_orders.py): the Glue Spark job
- [`template.yaml`](template.yaml): Glue job, trigger Lambda, EventBridge rules, SNS topic, curated tables
- `solve.sh`: uploads the script, deploys the stack, drops files, waits and checks

## Architecture

```
incoming/orders/*.csv ─► S3 (EventBridge enabled) ─► EventBridge rule "orders-landed"
                                                        │  (pattern: Object Created, key wildcard incoming/orders/*.csv)
                                                        ▼
                                         Lambda cq-da-05-start-etl ─► glue:StartJobRun(--source_key)
                                                                         │
                                Glue job cq-da-05-orders-etl ◄───────────┘
                                   ├─ valid rows ─► s3://curated/orders/order_date=YYYY-MM-DD/*.parquet
                                   └─ bad rows   ─► s3://curated/quarantine/*.json
Glue Job State Change (FAILED|TIMEOUT|ERROR) ─► EventBridge rule ─► SNS cq-da-05-etl-alerts ─► e-mail
```

## Design decisions

**S3 → EventBridge instead of S3 → Lambda notifications.** EventBridge gives
content filtering (prefix *and* suffix through `wildcard`), retries with a
dead-letter option, archive and replay, and fan-out to several targets. The
bucket only needs `EventBridgeEnabled: true`, which the lab stack already set.

**Lambda as the glue.** EventBridge can't call `glue:StartJobRun` with
per-event arguments directly. The 10-line Lambda passes the bucket and key as
job arguments. EventBridge can start a Glue **workflow** directly, but then you
need to read the event in the job through `get_workflow_run_properties`. That's a
fine alternative.

**`MaxConcurrentRuns: 10`.** The default is 1. Dropping three files at once
would make two `StartJobRun` calls fail with `ConcurrentRunsExceededException`.

**Explicit schema + PERMISSIVE + `_corrupt` column.** Spark doesn't fail on
bad rows. They arrive with nulls, and the raw text is kept in `_corrupt`. A
validity expression then splits good rows from bad. The job only *fails* on
infrastructure problems, which is when you want the SNS alert. Data problems
go to the quarantine for a human to look at.

**Partition projection on the curated table.** Concurrent job runs don't
need to update the Glue catalog (no race condition, no crawler), and each new
`order_date` folder is queryable immediately.

## Console steps (if you're building it by hand)

1. Upload `etl_orders.py` to `s3://<ScriptsBucket>/glue/`.
2. Glue, **ETL jobs > Script editor > Upload**. Role `cq-da-05-glue-job-role`,
   Glue 5.0, G.1X × 2, *Maximum concurrency* 10, job parameter
   `--curated_bucket=<CuratedBucket>`, bookmarks disabled.
3. Lambda, Python 3.12, use the existing role `cq-da-05-trigger-lambda-role`,
   paste the handler from `template.yaml` and set env var `JOB_NAME`.
4. EventBridge, **Rules > Create**, event pattern:
   ```json
   {"source":["aws.s3"],"detail-type":["Object Created"],
    "detail":{"bucket":{"name":["<LandingBucket>"]},
              "object":{"key":[{"wildcard":"incoming/orders/*.csv"}]}}}
   ```
   Target: the Lambda.
5. Create the curated table (`template.yaml`, resource `CuratedOrdersTable`) or the equivalent Athena DDL.
6. SNS topic + subscription, then a second rule on `aws.glue` / `Glue Job State Change` with state `FAILED`, `TIMEOUT` or `ERROR`.

## Known limitation (DIY)

De-duplication is **per file**. If the same order arrives in two different
files, both copies land in the curated table, and re-processing a file appends it
again. Production fixes:
- write to an **Apache Iceberg** table and `MERGE` on `order_id`, or
- record processed keys (for example in DynamoDB) and skip files you've already seen.
