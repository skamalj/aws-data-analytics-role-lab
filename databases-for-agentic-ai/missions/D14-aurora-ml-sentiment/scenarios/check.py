"""Self-check for D14: Aurora ML can reach Comprehend, sentiment is materialised, and the tool is fast and least-privileged."""
import json
import os
import sys
import time

import boto3

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "common"))
from checks import Db, check, finish, mission_outputs, rows, safe  # noqa: E402

out = mission_outputs(os.path.join(HERE, ".."))
admin, app = Db("admin"), Db("app")
rds = boto3.client("rds", region_name=out["region"])
lam = boto3.client("lambda", region_name=out["region"])

roles = rds.describe_db_clusters(DBClusterIdentifier=out["cluster_id"])["DBClusters"][0].get("AssociatedRoles", [])
check("an IAM role is associated with the cluster for the Comprehend feature",
      any(r.get("FeatureName") == "Comprehend" and r.get("Status") == "ACTIVE" for r in roles),
      json.dumps([{k: r.get(k) for k in ("FeatureName", "Status")} for r in roles]))

r, err = safe(admin.run, "SELECT sentiment FROM aws_comprehend.detect_sentiment('I love this tent, it is perfect!', 'en')")
check("SQL can call Comprehend (aws_comprehend.detect_sentiment)", r is not None and rows(r)[0]["sentiment"] == "POSITIVE", err or "")

for _ in range(12):                                     # the refresh job may still be running in the background
    r, err = safe(admin.run, "SELECT count(*) FILTER (WHERE sentiment IS NOT NULL) AS done, count(*) AS total FROM commerce.reviews")
    if r and rows(r)[0]["done"] == rows(r)[0]["total"]:
        break
    time.sleep(10)
st = rows(r)[0] if r else {}
check("sentiment is stored for all 600 reviews", st.get("done") == 600, err or json.dumps(st))

_, err = safe(app.run, "SELECT count(*) FROM commerce.reviews")
check("the agent identity cannot read raw reviews (curated view only)", err is not None, "" if err else "trail_desk_app can read commerce.reviews")

lam.invoke(FunctionName=out["tool_function"], Payload=json.dumps({"product_id": "P101"}).encode())   # warm-up
t0 = time.perf_counter()
resp = lam.invoke(FunctionName=out["tool_function"], Payload=json.dumps({"product_id": "P101"}).encode())
ms = (time.perf_counter() - t0) * 1000
body = json.loads(resp["Payload"].read())
total = sum(int(x.get("reviews", 0)) for x in body.get("sentiment", [])) if not resp.get("FunctionError") else 0
check("review_insights answers for P101 (33 reviews) in < 1 s without calling Comprehend",
      total == 33 and ms < 1000, f"{total} reviews, {ms:.0f} ms" + (f", {body.get('errorMessage')}" if resp.get("FunctionError") else ""))
finish()
