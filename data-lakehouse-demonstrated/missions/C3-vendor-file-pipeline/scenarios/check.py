"""C3 check: uploads trigger the pipeline, valid files are loaded and archived, invalid ones quarantined."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "common"))
from lh import Athena, check, finish, mission, safe, session  # noqa: E402

m = mission(os.path.join(HERE, ".."))
s3, sfn = session().client("s3"), session().client("stepfunctions")
cfg = s3.get_bucket_notification_configuration(Bucket=m["raw_bucket"])
check("the raw bucket sends events to EventBridge", "EventBridgeConfiguration" in cfg)
ex = sfn.list_executions(stateMachineArn=m["state_machine_arn"], maxResults=50)["executions"]
check("uploads start pipeline executions, and they succeed", ex and all(e["status"] == "SUCCEEDED" for e in ex[:3]) and len(ex) >= 3,
      f"{len(ex)} executions: " + ", ".join(e["status"] for e in ex[:5]))


def keys(prefix):
    return sorted(o["Key"].rsplit("/", 1)[-1] for o in s3.list_objects_v2(Bucket=m["raw_bucket"], Prefix=prefix).get("Contents", []))


check("valid files are archived in vendors/processed/", keys("vendors/processed/") == ["cairn-2026-03-04.csv", "northpine-2026-03-04.csv"],
      f"{keys('vendors/processed/')}")
check("the invalid file is quarantined in vendors/quarantine/", keys("vendors/quarantine/") == ["talus-2026-03-04.csv"], f"{keys('vendors/quarantine/')}")
check("nothing is left in vendors/incoming/", keys("vendors/incoming/") == [], f"{keys('vendors/incoming/')}")
r, err = safe(Athena().rows, "SELECT count(*) AS n, count(DISTINCT source_file) AS f FROM riverbend_lakehouse.vendor_shipments")
st = r[0] if r else {}
check("300 shipments from the 2 valid files are in vendor_shipments", st.get("n") == "300" and st.get("f") == "2", err or f"{st}")
finish()
