"""Create the schema, sample data and database roles in the shared cluster (idempotent)."""
import json
import os
import sys

import boto3

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "common"))
from dbsql import Db, base_outputs  # noqa: E402

out = base_outputs()
db = Db("admin", out)
sm = boto3.client("secretsmanager", region_name=out["region"])
pw = {k: json.loads(sm.get_secret_value(SecretId=out[f"{k}_secret_arn"])["SecretString"])["password"]
      for k in ("app", "kb", "diag")}
print(">> schema");  db.run_file(os.path.join(HERE, "db", "01_schema.sql"))
print(">> data");    db.run_file(os.path.join(HERE, "db", "02_data.sql"))
print(">> roles");   db.run_file(os.path.join(HERE, "db", "03_roles.sql"), quiet=True,
                                 subst={"APP_PASSWORD": pw["app"], "KB_PASSWORD": pw["kb"], "DIAG_PASSWORD": pw["diag"]})
r = db.run("SELECT (SELECT count(*) FROM commerce.customers), (SELECT count(*) FROM commerce.orders), "
           "(SELECT count(*) FROM commerce.order_lines)")
c, o, l = [list(v.values())[0] for v in r["records"][0]]
print(f">> seeded {c} customers, {o} orders, {l} order lines")
