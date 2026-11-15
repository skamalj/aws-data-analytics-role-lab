"""
Environment loader for C4 (not part of the challenge): writes 20,000,000 point-of-sale rows for
Jan-Mar 2026 into riverbend_lakehouse.sales the way the legacy streaming loader did - in 10 small
appends, every task writing into every daily partition.
Arguments: --database --table
"""
import sys

from pyspark.sql import functions as F

N, BATCHES = 20_000_000, 10
REGIONS = ["NA", "EU", "APAC", "LATAM"]


def load(spark, table):
    spark.conf.set("spark.sql.session.timeZone", "UTC")
    spark.sql(f"ALTER TABLE {table} SET TBLPROPERTIES ('write.distribution-mode' = 'none')")
    step = N // BATCHES
    for b in range(BATCHES):
        df = (spark.range(b * step + 1, (b + 1) * step + 1)
              .select(F.col("id").alias("sale_id"),
                      F.timestamp_seconds(F.lit(1767225600) + (F.col("id") * 7919) % 7776000).cast("timestamp_ntz").alias("sold_at"),
                      F.concat(F.lit("S"), F.lpad((F.col("id") % 50).cast("string"), 2, "0")).alias("store_id"),
                      F.element_at(F.array(*[F.lit(r) for r in REGIONS]), ((F.col("id") % 50) % 4 + 1).cast("int")).alias("region"),
                      F.concat(F.lit("P"), (F.lit(101) + F.col("id") % 18).cast("string")).alias("product_id"),
                      (F.lit(1) + F.col("id") % 3).cast("int").alias("quantity"),
                      (F.lit(10.99) + (F.col("id") * 31) % 500).cast("double").alias("amount"))
              .repartition(40))
        df.writeTo(table).append()
        print(f"[load_sales] batch {b + 1}/{BATCHES} appended")


if __name__ == "__main__":
    from awsglue.context import GlueContext
    from awsglue.utils import getResolvedOptions
    from pyspark.context import SparkContext

    args = getResolvedOptions(sys.argv, ["JOB_NAME", "database", "table"])
    load(GlueContext(SparkContext.getOrCreate()).spark_session, f"glue_catalog.{args['database']}.{args['table']}")
