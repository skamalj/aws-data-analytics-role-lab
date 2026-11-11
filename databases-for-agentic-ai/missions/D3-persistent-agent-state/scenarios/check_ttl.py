"""Check that checkpoint items carry a TTL attribute that the table actually uses."""
import json
import os
import subprocess
import sys
import time

import boto3

here = os.path.dirname(os.path.abspath(__file__))
out = json.loads(subprocess.run(["terraform", f"-chdir={here}/../terraform", "output", "-json"],
                                capture_output=True, text=True).stdout)
table = out["checkpoint_table"]["value"]
region = out["runtime_arn"]["value"].split(":")[3]
ddb = boto3.client("dynamodb", region_name=region)
ttl = ddb.describe_time_to_live(TableName=table)["TimeToLiveDescription"]
attr = ttl.get("AttributeName")
print(f"table TTL: {ttl.get('TimeToLiveStatus')} on attribute '{attr}'")
items = ddb.scan(TableName=table, Limit=50)["Items"]
if not items:
    sys.exit("no checkpoint items yet - have a conversation first")
with_attr = [i for i in items if attr in i and "N" in i[attr]]
print(f"{len(with_attr)}/{len(items)} sampled items have a numeric '{attr}'")
if with_attr:
    secs = int(with_attr[0][attr]["N"]) - int(time.time())
    print(f"example item expires in {secs / 86400:.1f} days")
ok = ttl.get("TimeToLiveStatus") == "ENABLED" and len(with_attr) == len(items)
print("TTL:", "PASS" if ok else "FAIL")
