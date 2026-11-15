"""
Replay the order-status CDC stream into Firehose: 200 inserts, then 120 updates, then 60 updates + 20 deletes.
Each run first empties riverbend_lakehouse.order_status and the error prefix, so it's repeatable.

    python3 missions/C7-firehose-iceberg-upserts/scenarios/stream_orders.py [--wait 120]
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "common"))
from datagen import order_status_waves  # noqa: E402
from lh import Athena, base, mission, safe, session  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--wait", type=int, default=120, help="seconds between waves (Firehose buffers for 60 s)")
args = ap.parse_args()
b, o = base(), mission(os.path.join(HERE, ".."))
s = session()
fh, s3 = s.client("firehose"), s.client("s3")

print("reset: empty order_status and the error prefix")
_, err = safe(Athena().run, "DELETE FROM riverbend_lakehouse.order_status WHERE true")
print(f"  {err or 'table emptied'}")
for page in s3.get_paginator("list_objects_v2").paginate(Bucket=b["lake_bucket"], Prefix=o["error_prefix"]):
    keys = [{"Key": x["Key"]} for x in page.get("Contents", [])]
    if keys:
        s3.delete_objects(Bucket=b["lake_bucket"], Delete={"Objects": keys})

waves, _ = order_status_waves()
for i, wave in enumerate(waves, 1):
    failed = 0
    for j in range(0, len(wave), 500):
        recs = [{"Data": (json.dumps(e) + "\n").encode()} for e in wave[j:j + 500]]
        failed += fh.put_record_batch(DeliveryStreamName=o["stream_name"], Records=recs)["FailedPutCount"]
    ops = {}
    for e in wave:
        ops[e["op"]] = ops.get(e["op"], 0) + 1
    print(f"wave {i}: sent {len(wave)} records {ops}, {failed} rejected by Firehose")
    print(f"  waiting {args.wait}s for the buffer to flush and commit", flush=True)
    time.sleep(args.wait)
print("done - run scenarios/check.py (errors, if any, are in "
      f"s3://{b['lake_bucket']}/{o['error_prefix']} and CloudWatch Logs {o['log_group']})")
