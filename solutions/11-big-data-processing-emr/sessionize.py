"""
Spark job (Amazon EMR / EMR Serverless): rebuild web sessions from raw clickstream.

Rule: events of the same customer on the same device belong to one session until there is a
gap of more than 30 minutes. A session belongs to the date (UTC) on which it started.

    spark-submit sessionize.py s3://<DataBucket>/clickstream/ s3://<DataBucket>/curated/sessions/
"""
import sys

from pyspark.sql import SparkSession, Window
from pyspark.sql import functions as F

src, dst = sys.argv[1], sys.argv[2]
GAP_SECONDS = 30 * 60

spark = (SparkSession.builder.appName("riverbend-sessionize")
         .config("spark.sql.session.timeZone", "UTC")
         .enableHiveSupport()          # Glue Data Catalog as the metastore (see sparkSubmitParameters)
         .getOrCreate())

events = (spark.read.json(src)                       # dt=... folders become a column; we don't need it
          .drop("dt")
          .withColumn("ts", F.to_timestamp("event_ts")))

w = Window.partitionBy("customer_id", "device").orderBy("ts")
flagged = (events
           .withColumn("prev_ts", F.lag("ts").over(w))
           .withColumn("is_new", F.when(F.col("prev_ts").isNull() |
                                        ((F.col("ts").cast("long") - F.col("prev_ts").cast("long")) > GAP_SECONDS), 1)
                       .otherwise(0))
           .withColumn("session_seq", F.sum("is_new").over(w.rowsBetween(Window.unboundedPreceding, 0))))

sessions = (flagged.groupBy("customer_id", "device", "session_seq")
            .agg(F.min("ts").alias("session_start"),
                 F.max("ts").alias("session_end"),
                 F.count("*").alias("events"),
                 F.sum(F.when(F.col("event_type") == "page_view", 1).otherwise(0)).alias("page_views"),
                 F.sum(F.when(F.col("event_type") == "search", 1).otherwise(0)).alias("searches"),
                 F.sum(F.when(F.col("event_type") == "add_to_cart", 1).otherwise(0)).alias("add_to_carts"),
                 F.sum(F.when(F.col("event_type") == "checkout", 1).otherwise(0)).alias("checkouts"))
            .withColumn("session_id", F.substring(F.sha2(F.concat_ws("|", "customer_id", "device",
                                                                     F.col("session_start").cast("string")), 256), 1, 16))
            .withColumn("duration_s", F.col("session_end").cast("long") - F.col("session_start").cast("long"))
            .withColumn("converted", F.col("checkouts") > 0)
            .withColumn("dt", F.to_date("session_start"))
            .drop("session_seq")
            .select("session_id", "customer_id", "device", "session_start", "session_end", "duration_s",
                    "events", "page_views", "searches", "add_to_carts", "checkouts", "converted", "dt"))

(sessions.repartition("dt")
 .write.mode("overwrite")
 .partitionBy("dt")
 .format("parquet")
 .option("path", dst)
 .saveAsTable("riverbend_emr.sessions"))

print(f"[sessionize] wrote {sessions.count()} sessions to {dst}")
spark.stop()
