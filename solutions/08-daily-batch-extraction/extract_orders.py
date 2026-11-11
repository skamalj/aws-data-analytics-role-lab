"""
Glue Spark job: extract orders from Aurora PostgreSQL into the lake.

  --mode full         snapshot of every row with updated_at < run_date + 1 day
  --mode incremental  only rows whose updated_at falls on run_date (new + changed rows)

Output: s3://<extract_bucket>/orders_changes/extract_date=<run_date>/  (overwritten, so re-runs are idempotent)
"""
import json
import sys
from datetime import date, timedelta

import boto3
from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from pyspark.sql import functions as F

args = getResolvedOptions(sys.argv, ["JOB_NAME", "run_date", "mode", "db_host", "db_name",
                                     "secret_arn", "extract_bucket"])
sc = SparkContext()
glue = GlueContext(sc)
spark = glue.spark_session
job = Job(glue)
job.init(args["JOB_NAME"], args)

run_date = date.fromisoformat(args["run_date"])
next_day = run_date + timedelta(days=1)

# Credentials come from Secrets Manager (through the VPC interface endpoint), never from job parameters.
secret = json.loads(boto3.client("secretsmanager").get_secret_value(SecretId=args["secret_arn"])["SecretString"])

if args["mode"] == "full":
    where = f"updated_at < TIMESTAMP '{next_day}'"
elif args["mode"] == "incremental":
    where = f"updated_at >= TIMESTAMP '{run_date}' AND updated_at < TIMESTAMP '{next_day}'"
else:
    raise ValueError("--mode must be full or incremental")

query = f"SELECT * FROM sales.orders WHERE {where}"   # the filter runs inside PostgreSQL (push-down)
print(f"[extract] {query}")

df = (spark.read.format("jdbc")
      .option("url", f"jdbc:postgresql://{args['db_host']}:5432/{args['db_name']}")
      .option("driver", "org.postgresql.Driver")
      .option("user", secret["username"])
      .option("password", secret["password"])
      .option("query", query)
      .option("fetchsize", 5000)
      .load()
      .withColumn("extracted_at", F.current_timestamp()))

target = f"s3://{args['extract_bucket']}/orders_changes/extract_date={run_date}/"
rows = df.count()
df.coalesce(1).write.mode("overwrite").parquet(target)
print(f"[extract] wrote {rows} rows to {target}")
job.commit()
