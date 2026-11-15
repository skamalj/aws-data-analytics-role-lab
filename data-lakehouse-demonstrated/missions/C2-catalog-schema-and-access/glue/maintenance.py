"""
Glue 5.0 job: run the Spark SQL statements in a file (one statement per ';'-terminated block) against
the Glue catalog - the team's tool for Iceberg DDL that Athena doesn't support.
Arguments: --sql_path s3://.../maintenance.sql
In the statements, refer to tables as glue_catalog.riverbend_lakehouse.<table>.
"""
import sys


def statements(text):
    body = "\n".join(l for l in text.splitlines() if not l.strip().startswith("--"))
    return [s.strip() for s in body.split(";") if s.strip()]


def run(spark, text):
    for s in statements(text):
        print(f"[maintenance] {s.splitlines()[0][:120]}")
        for row in spark.sql(s).collect()[:20]:
            print(f"    {row}")


if __name__ == "__main__":
    import boto3
    from awsglue.context import GlueContext
    from awsglue.utils import getResolvedOptions
    from pyspark.context import SparkContext

    args = getResolvedOptions(sys.argv, ["JOB_NAME", "sql_path"])
    bucket, key = args["sql_path"][5:].split("/", 1)
    text = boto3.client("s3").get_object(Bucket=bucket, Key=key)["Body"].read().decode()
    run(GlueContext(SparkContext.getOrCreate()).spark_session, text)
