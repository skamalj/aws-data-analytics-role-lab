"""
Glue 5.0 job: load one validated vendor CSV into the Iceberg table riverbend_lakehouse.vendor_shipments.
Arguments: --source_bucket  --source_key  --database  --table
"""
import sys

from pyspark.sql import functions as F


def load(spark, path, table, source_file):
    df = (spark.read.option("header", True).csv(path)
          .withColumn("quantity", F.col("quantity").cast("int"))
          .withColumn("shipped_at", F.to_timestamp("shipped_at"))
          .withColumn("source_file", F.lit(source_file))
          .dropDuplicates(["shipment_id"]))
    df.createOrReplaceTempView("incoming")
    spark.sql(f"""MERGE INTO {table} t USING incoming s ON t.shipment_id = s.shipment_id
                  WHEN MATCHED THEN UPDATE SET * WHEN NOT MATCHED THEN INSERT *""")
    return df.count()


if __name__ == "__main__":
    from awsglue.context import GlueContext
    from awsglue.job import Job
    from awsglue.utils import getResolvedOptions
    from pyspark.context import SparkContext

    args = getResolvedOptions(sys.argv, ["JOB_NAME", "source_bucket", "source_key", "database", "table"])
    glue = GlueContext(SparkContext.getOrCreate())
    job = Job(glue)
    job.init(args["JOB_NAME"], args)
    n = load(glue.spark_session, f"s3://{args['source_bucket']}/{args['source_key']}",
             f"glue_catalog.{args['database']}.{args['table']}", args["source_key"].rsplit("/", 1)[-1])
    print(f"[vendor_load] {args['source_key']}: {n} shipments merged")
    job.commit()
