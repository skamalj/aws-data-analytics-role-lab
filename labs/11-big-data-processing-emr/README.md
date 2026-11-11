# Lab 11: Big Data Processing with Amazon EMR

## Scenario

A tracking-library upgrade on Riverbend's website **stopped sending session ids**.
Two weeks of raw clickstream (about 170k events, gzip JSON) sit in S3 without them. Product
managers need session metrics for that period: sessions, conversion rate by
device, session duration and bounce rate. The data team expects this dataset to
grow to billions of rows, so the solution must be a distributed **Apache Spark** job on
**Amazon EMR**, not a script on a laptop.

## What the starting environment gives you

`./scripts/deploy.sh 11-big-data-processing-emr` creates:

| Resource | Notes |
|---|---|
| `DataBucket` | `clickstream/dt=2024-06-01/ … dt=2024-06-15/events-00N.json.gz` |
| `CodeBucket` | Upload your job script here. Also for Spark logs (`logs/`) |
| IAM role `cq-da-11-emr-job-role` | Job runtime role: S3 on both buckets, Glue catalog on `riverbend_emr` |
| Glue database `riverbend_emr`, Athena workgroup `cq-da-11` | |

Event example (no session id):

```json
{"event_ts":"2024-06-03T14:02:11.000Z","customer_id":"C00123","device":"ios","event_type":"add_to_cart","product_id":"P107"}
```

## Your tasks

1. Create an **EMR Serverless** Spark application `cq-da-11-spark` (latest EMR 7.x release),
   with auto-stop after 5 idle minutes and a maximum capacity of 16 vCPU / 64 GB.
2. Write and run a **PySpark job** that rebuilds sessions:
   - a session is a run of events by the same **customer on the same device**, with no gap longer than **30 minutes**
   - one output row per session: `session_id` (deterministic), `customer_id`, `device`,
     `session_start`, `session_end`, `duration_s`, `events`, counts per event type, `converted` (at least one checkout)
   - a session belongs to the **UTC date it started**, as partition column `dt`
   - write Parquet to `s3://<DataBucket>/curated/sessions/` **and** register the table `riverbend_emr.sessions`
     in the Glue Data Catalog from Spark itself (no crawler)
3. In **Athena**, report:
   - total sessions, conversion %, average duration and average events per session
   - conversion and duration per device
   - the number of bounce sessions (1 event)
4. Open the **Spark UI** for your job run. Which stage shuffles data, and why?
5. Question: the same job runs every night on 2 TB. When would you move it to an EMR on EC2
   cluster with Spot instances instead of EMR Serverless?

## How you know you're done

Numbers match [`expected-results.md`](../../solutions/11-big-data-processing-emr/expected-results.md) exactly. The data is deterministic.

## Hints

<details><summary>Sessionization in Spark</summary>Window functions: <code>lag()</code> to get the previous event time per customer and device, a 0/1 "new session" flag, then a running <code>sum()</code> over the flag gives a session number.</details>
<details><summary>Using the Glue Data Catalog from EMR Serverless</summary>Spark property <code>spark.hadoop.hive.metastore.client.factory.class=com.amazonaws.glue.catalog.metastore.AWSGlueDataCatalogHiveClientFactory</code> plus <code>enableHiveSupport()</code>, then <code>saveAsTable</code>.</details>

## DIY challenge

- Run the same script as a step on a small **EMR on EC2** cluster (1 primary + 2 core, Spot), and compare its cost and start-up time.
- Write the output as an **Apache Iceberg** table and make the job incremental (process one new day at a time).

## Cleanup

```bash
./solutions/11-big-data-processing-emr/cleanup.sh
./scripts/destroy.sh 11-big-data-processing-emr
```

**Cost:** about $0.05–0.15 per job run. An idle application that has auto-stopped costs nothing.
