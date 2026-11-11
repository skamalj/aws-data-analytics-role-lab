"""
Glue Spark job: clean one landed orders CSV file and append it to the curated
Parquet table.

Arguments: --source_bucket --source_key --curated_bucket
"""
import os
import sys

from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from pyspark.sql import functions as F
from pyspark.sql import types as T

args = getResolvedOptions(sys.argv, ["JOB_NAME", "source_bucket", "source_key", "curated_bucket"])
sc = SparkContext()
glue = GlueContext(sc)
spark = glue.spark_session
job = Job(glue)
job.init(args["JOB_NAME"], args)

src = f"s3://{args['source_bucket']}/{args['source_key']}"
curated = f"s3://{args['curated_bucket']}"
source_file = os.path.basename(args["source_key"])

schema = T.StructType([
    T.StructField("order_id", T.StringType()),
    T.StructField("order_ts", T.TimestampType()),
    T.StructField("customer_id", T.StringType()),
    T.StructField("product_id", T.StringType()),
    T.StructField("quantity", T.IntegerType()),
    T.StructField("unit_price", T.DoubleType()),
    T.StructField("discount", T.DoubleType()),
    T.StructField("total_amount", T.DoubleType()),
    T.StructField("channel", T.StringType()),
    T.StructField("store_id", T.StringType()),
    T.StructField("region", T.StringType()),
    T.StructField("status", T.StringType()),
    T.StructField("_corrupt", T.StringType()),
])

raw = (spark.read
       .option("header", True)
       .option("mode", "PERMISSIVE")
       .option("columnNameOfCorruptRecord", "_corrupt")
       .option("timestampFormat", "yyyy-MM-dd HH:mm:ss")
       .schema(schema)
       .csv(src)
       .cache())  # Spark requires caching before filtering on the corrupt-record column

is_valid = (
    F.col("_corrupt").isNull()
    & F.col("order_id").isNotNull() & (F.length("order_id") > 0)
    & F.col("order_ts").isNotNull()
    & F.col("quantity").isNotNull() & (F.col("quantity") > 0)
    & F.col("total_amount").isNotNull() & (F.col("total_amount") >= 0)
    & F.col("region").isin("NA", "EU", "APAC", "LATAM")
    & F.col("status").isin("COMPLETED", "RETURNED", "CANCELLED")
)

bad = raw.filter(~is_valid)
good = (raw.filter(is_valid)
        .filter(F.col("status") != "CANCELLED")
        .dropDuplicates(["order_id"])
        .drop("_corrupt")
        .withColumn("source_file", F.lit(source_file))
        .withColumn("ingest_ts", F.current_timestamp())
        .withColumn("order_date", F.to_date("order_ts")))

good_count, bad_count = good.count(), bad.count()
print(f"[etl] {src}: {raw.count()} rows read, {good_count} curated, {bad_count} quarantined")

if good_count:
    good.write.mode("append").partitionBy("order_date").parquet(f"{curated}/orders/")
if bad_count:
    (bad.withColumn("source_file", F.lit(source_file))
        .withColumn("quarantined_at", F.current_timestamp())
        .write.mode("append").json(f"{curated}/quarantine/"))

job.commit()
