"""After destroy: remove tables the (broken) inspector may have created on its own."""
import subprocess

import boto3

region = subprocess.run(["aws", "configure", "get", "region"], capture_output=True, text=True).stdout.strip() or "us-west-2"
ddb = boto3.client("dynamodb", region_name=region)
for t in ddb.list_tables()["TableNames"]:
    if t.startswith("riverbend-d7-"):
        print(f"deleting stray table {t}")
        ddb.delete_table(TableName=t)
