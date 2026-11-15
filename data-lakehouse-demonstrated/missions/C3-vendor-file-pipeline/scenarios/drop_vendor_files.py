"""
Scenario driver: three vendors upload their daily shipment files to vendors/incoming/
(two valid, one missing the quantity column). Then wait up to ~10 minutes for the pipeline.
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "common"))
import datagen  # noqa: E402
from lh import mission, session  # noqa: E402

m = mission(os.path.join(HERE, ".."))
s3, sfn = session().client("s3"), session().client("stepfunctions")
started = time.time()
for name, body in datagen.vendor_files().items():
    s3.put_object(Bucket=m["raw_bucket"], Key=f"vendors/incoming/{name}", Body=body.encode())
    print(f"  uploaded vendors/incoming/{name}")
print("  waiting for the pipeline", end="", flush=True)
for _ in range(40):
    time.sleep(15)
    ex = [e for e in sfn.list_executions(stateMachineArn=m["state_machine_arn"], maxResults=20)["executions"]
          if e["startDate"].timestamp() >= started - 5]
    print(".", end="", flush=True)
    if len(ex) >= 3 and all(e["status"] != "RUNNING" for e in ex):
        break
print()
for e in ex if "ex" in dir() else []:
    print(f"  execution {e['name'][:36]}: {e['status']}")
if not ex:
    print("  no executions were started - is anything listening for these uploads?")
