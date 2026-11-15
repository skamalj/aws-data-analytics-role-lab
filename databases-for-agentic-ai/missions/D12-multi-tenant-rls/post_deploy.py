"""Create the saas_app identity and the tenant table (run by ./scripts/deploy.sh D12 after terraform)."""
import json
import os
import sys

import boto3

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "common"))
from checks import mission_outputs  # noqa: E402
from dbsql import Db  # noqa: E402

out = mission_outputs(HERE)
db = Db("admin")
pw = json.loads(boto3.client("secretsmanager", region_name=db.o["region"]).get_secret_value(
    SecretId=out["saas_secret_arn"])["SecretString"])["password"]
db.run_file(os.path.join(HERE, "db", "tenancy.sql"), subst={"SAAS_PASSWORD": pw}, quiet=True)
print("  saas.tenant_docs ready (20 tenants x 1,500 docs)")
