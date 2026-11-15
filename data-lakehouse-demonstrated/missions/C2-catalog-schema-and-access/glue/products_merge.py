"""
Glue 5.0 job: merge the supplier product feed (JSON Lines) into the Iceberg table riverbend_lakehouse.products.
Arguments: --source_path s3://.../suppliers/feed=v2/   --database riverbend_lakehouse   --table products
"""
import sys


def merge(spark, source_path, table):
    feed = spark.read.json(source_path)
    feed.createOrReplaceTempView("feed")
    spark.sql(f"""
        MERGE INTO {table} t
        USING feed s
        ON t.product_id = s.product_id
        WHEN MATCHED THEN UPDATE SET *
        WHEN NOT MATCHED THEN INSERT *
    """)
    return feed.count()


if __name__ == "__main__":
    from awsglue.context import GlueContext
    from awsglue.job import Job
    from awsglue.utils import getResolvedOptions
    from pyspark.context import SparkContext

    args = getResolvedOptions(sys.argv, ["JOB_NAME", "source_path", "database", "table"])
    glue = GlueContext(SparkContext.getOrCreate())
    job = Job(glue)
    job.init(args["JOB_NAME"], args)
    n = merge(glue.spark_session, args["source_path"], f"glue_catalog.{args['database']}.{args['table']}")
    print(f"[products_merge] merged {n} feed rows")
    job.commit()
