"""Upload sql/maintenance.sql and run it with the Spark maintenance job (for Iceberg DDL Athena can't do)."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "common"))
from lh import base, mission, run_glue, session  # noqa: E402

b, m = base(), mission(os.path.join(HERE, ".."))
key = "c4/maintenance.sql"
session().client("s3").upload_file(os.path.join(HERE, "..", "sql", "maintenance.sql"), b["scripts_bucket"], key)
run_glue(m["maintenance_job"], {"--sql_path": f"s3://{b['scripts_bucket']}/{key}"})
