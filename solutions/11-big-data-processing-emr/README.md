# Lab 11 solution: Big Data Processing with Amazon EMR

Files: [`sessionize.py`](sessionize.py) (PySpark), [`queries.sql`](queries.sql), `solve.sh` (EMR Serverless via the CLI).

## The algorithm (gaps and islands)

```
partition by (customer_id, device), order by ts
is_new      = 1 if first event OR ts - lag(ts) > 30 min, else 0
session_seq = running SUM(is_new)            ← every new session increments the counter
group by (customer_id, device, session_seq)  → one row per session
```

This is a single shuffle (on `customer_id, device`) followed by window functions. That's
why it scales to billions of events, where a self-join wouldn't.
`session_id` is a deterministic hash of customer, device and start, so re-running the job yields the same ids.

## EMR Serverless vs EMR on EC2

| | EMR Serverless (used here) | EMR on EC2 cluster |
|---|---|---|
| Capacity | Workers start per job and auto-stop when idle (5-minute idle timeout here) | You choose instance types and counts, or use managed scaling |
| Billing | vCPU-seconds + GB-seconds actually used | EC2 + EMR fee while the cluster is up, even when idle |
| Good for | Spiky or scheduled batch jobs, no ops | Long-running clusters, custom AMIs, HBase/Presto/Flink, tuning access, Spot fleets |
| Networking | Optional VPC | Always in your VPC |

The same `sessionize.py` runs unchanged on an EMR on EC2 cluster
(`spark-submit` as a step, with *Use AWS Glue Data Catalog for table metadata* ticked).

## Glue Data Catalog as metastore

`enableHiveSupport()` + `spark.hadoop.hive.metastore.client.factory.class=…AWSGlueDataCatalogHiveClientFactory`
means `saveAsTable("riverbend_emr.sessions")` creates the table **and its 14
partitions** in Glue. Athena (and Redshift Spectrum) can query it straight away, with no crawler.

## Console path

1. **EMR > EMR Serverless > Get started / EMR Studio > Applications > Create**: type Spark,
   latest `emr-7.x`, *auto-stop after 5 minutes idle*, and limit capacity to 16 vCPU / 64 GB.
2. **Submit job run**: runtime role `cq-da-11-emr-job-role`, script `s3://<CodeBucket>/jobs/sessionize.py`,
   arguments `s3://<DataBucket>/clickstream/` and `s3://<DataBucket>/curated/sessions/`, the Spark properties from
   `solve.sh`, and S3 logs at `s3://<CodeBucket>/logs/`.
3. Open the **Spark UI** from the job run to see the stages: read, exchange (shuffle), window, write.

## Cost

About 2 executors × 2 vCPU + a driver for ~3–5 minutes: roughly **$0.05–0.15** per run.
`totalResourceUtilization` in `get-job-run` shows exactly what was billed.
