# Lab 08 solution: Daily Batch Extraction

Files: [`extract_orders.py`](extract_orders.py) (Glue job), [`template.yaml`](template.yaml)
(connection, job, table, state machine, schedule), [`queries.sql`](queries.sql), `solve.sh`.

## Architecture

```
EventBridge Scheduler (01:30 UTC) ─► Step Functions cq-da-08-daily-batch
   ResolveParameters  run_date = input.run_date or yesterday; mode = incremental
   Extract            glue:startJobRun.sync ─► Glue job (ENIs in private subnet, Glue SG)
                                                  │ JDBC 5432 (DB SG allows Glue SG only)
                                                  ▼
                                    Aurora PostgreSQL: SELECT ... WHERE updated_at on run_date
                                                  │ Parquet via S3 gateway endpoint
                                                  ▼
                            s3://extracts/orders_changes/extract_date=YYYY-MM-DD/ (overwrite)
   CountRows/GetCount athena:startQueryExecution.sync + getQueryResults
   NotifySuccess      sns:publish   ── on any error: NotifyFailure ─► Fail
```

## Networking: why each piece is there

| Piece | Reason |
|---|---|
| Glue **connection** with subnet + security group | Glue creates ENIs for the job in your VPC, so it can reach a private database |
| **Self-referencing** inbound rule on the Glue SG | Spark executors on those ENIs talk to each other. Glue refuses to start without it |
| DB SG allows 5432 **from the Glue SG** | Least privilege: no CIDR ranges, and the database isn't public |
| **S3 gateway endpoint** | Job ENIs have no internet route. Glue needs S3 for scripts, temp files and output |
| **Secrets Manager / Glue interface endpoints** | The job reads the DB secret, and Glue calls its own API, from inside the VPC |

There's no NAT gateway and no internet access anywhere. This is the usual setup for regulated workloads.

## Incremental extraction pattern

- **High-water mark on `updated_at`.** Each run extracts one closed day. It catches inserts
  *and* updates, which a filter on `order_ts` or a "max(order_id)" approach misses.
  Deletes aren't captured. For those you need soft deletes or CDC (AWS DMS, or the
  zero-ETL integration to Redshift).
- **Push-down.** The `query` option runs the `WHERE` in PostgreSQL. Reading the whole
  table and filtering in Spark would move every row over the network every night.
- **Idempotent writes.** Each run overwrites exactly one `extract_date=` partition, so
  retries and re-runs (backfills) are safe. Compare this with Glue job bookmarks:
  convenient, but much harder to re-run one specific day.
- **Current-state view.** `ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY updated_at DESC)`
  over all extracts reconstructs the source table in the lake. Many teams `MERGE`
  into an Iceberg table instead.

## Step Functions notes

- `.sync` integrations wait for the Glue job or Athena query to finish. You don't need polling loops.
- The JSONata query language computes "yesterday" with `$now()`/`$fromMillis`,
  so the scheduler can send `{}` and manual backfills can pass `{"run_date": "..."}`.
- The schedule is created **DISABLED**, because the sample data is in 2024. Enable it to see a real nightly run, which will extract 0 rows.
