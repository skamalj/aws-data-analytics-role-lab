"""
Generate the identity security events the detections must catch:
  1. a rogue operator (no permissions) repeatedly tries to mint workload access tokens for the canary agent
  2. someone re-tags the canary workload identity (then puts it back)
CloudTrail delivers to CloudWatch Logs within ~5-15 minutes; then run check.py.
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "common"))
from sai import mission, safe, session  # noqa: E402

o = mission(os.path.join(HERE, ".."))
rogue = session(o["rogue_role_arn"]).client("bedrock-agentcore")
for i in range(3):
    _, err = safe(rogue.get_workload_access_token, workloadName=o["canary_name"])
    print(f"rogue GetWorkloadAccessToken #{i + 1}: {err or 'SUCCEEDED (it should not!)'}")
    _, err = safe(rogue.get_workload_access_token_for_user_id, workloadName=o["canary_name"], userId="cfo")
    print(f"rogue GetWorkloadAccessTokenForUserId #{i + 1}: {err or 'SUCCEEDED (it should not!)'}")
ctl = session().client("bedrock-agentcore-control")
_, err = safe(ctl.tag_resource, resourceArn=o["canary_arn"], tags={"team": "trading"})
print(f"re-tag canary team=trading: {err or 'done'}")
time.sleep(2)
_, err = safe(ctl.tag_resource, resourceArn=o["canary_arn"], tags={"team": "canary"})
print(f"restore canary team=canary: {err or 'done'}")
print(f"\nevents sent at {time.strftime('%H:%M:%S')}. Wait ~5-15 minutes, then: python3 {os.path.relpath(os.path.join(HERE, 'check.py'))}")
