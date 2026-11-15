"""
Scenario driver: empty the orders table, deliver the three daily exports to S3 and run the ingestion
job once per day, in order - exactly what the nightly schedule does.

    python3 missions/C1-order-ingestion-duplicates/scenarios/deliver_and_ingest.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "common"))
import datagen  # noqa: E402
from lh import Athena, base, mission, run_glue, session  # noqa: E402

b, m = base(), mission(os.path.join(HERE, ".."))
s3 = session().client("s3")
Athena().run("DELETE FROM riverbend_lakehouse.orders WHERE true")
print("  orders table emptied")
for day, rows in sorted(datagen.order_deliveries().items()):
    key = f"orders/dt={day}/export.json"
    s3.put_object(Bucket=b["raw_bucket"], Key=key, Body="".join(json.dumps(r) + "\n" for r in rows).encode())
    print(f"  delivered s3://{b['raw_bucket']}/{key} ({len(rows)} lines)")
    r = run_glue(m["job_name"], {"--source_path": f"s3://{b['raw_bucket']}/orders/dt={day}/",
                                  "--database": b["database"], "--table": "orders"})
    if r["JobRunState"] != "SUCCEEDED":
        sys.exit("ingestion failed - fix it, then run this script again")
print("done - now run scenarios/check.py")
