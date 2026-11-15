"""
Glue 5.0 job: load one day's order export (JSON Lines) into the Iceberg table riverbend_lakehouse.orders.

Arguments: --source_path s3://.../orders/dt=YYYY-MM-DD/   --database riverbend_lakehouse   --table orders

Exports are messy: the same order can appear several times in one file (re-sent lines, several status
changes on the same day), later files contain status updates of earlier orders, and the export system
occasionally replays old files.
"""
import sys

from pyspark.sql import Window
from pyspark.sql import functions as F


def ingest(spark, source_path, table):
    src = (spark.read.json(source_path)
           .withColumn("order_ts", F.to_timestamp("order_ts"))
           .withColumn("updated_at", F.to_timestamp("updated_at"))
           .withColumn("quantity", F.col("quantity").cast("int"))
           .withColumn("amount", F.col("amount").cast("double"))
           .select("order_id", "customer_id", "product_id", "quantity", "amount", "region", "status",
                   "order_ts", "updated_at"))

    # one row per order from this batch
    w = Window.partitionBy("order_id").orderBy(F.col("updated_at").asc())
    latest = src.withColumn("rn", F.row_number().over(w)).filter("rn = 1").drop("rn")
    latest.createOrReplaceTempView("incoming")

    spark.sql(f"""
        MERGE INTO {table} t
        USING incoming s
        ON t.order_id = s.order_id AND t.updated_at = s.updated_at
        WHEN MATCHED THEN UPDATE SET *
        WHEN NOT MATCHED THEN INSERT *
    """)
    return src.count(), latest.count()


if __name__ == "__main__":
    from awsglue.context import GlueContext
    from awsglue.job import Job
    from awsglue.utils import getResolvedOptions
    from pyspark.context import SparkContext

    args = getResolvedOptions(sys.argv, ["JOB_NAME", "source_path", "database", "table"])
    glue = GlueContext(SparkContext.getOrCreate())
    job = Job(glue)
    job.init(args["JOB_NAME"], args)
    read, merged = ingest(glue.spark_session, args["source_path"], f"glue_catalog.{args['database']}.{args['table']}")
    print(f"[orders_ingest] {args['source_path']}: {read} rows read, {merged} rows merged")
    job.commit()
