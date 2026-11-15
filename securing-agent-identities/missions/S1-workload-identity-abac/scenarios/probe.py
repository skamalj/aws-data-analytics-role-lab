"""Try to mint a workload access token for every agent as every team's operator (the access matrix)."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "common"))
from sai import mission, safe, session  # noqa: E402

o = mission(os.path.join(HERE, ".."))
ids = o["workload_identities"]
print(f"{'operator':<12}" + "".join(f"{v['name']:<38}" for v in ids.values()))
for team, arn in o["ops_role_arns"].items():
    dp = session(arn).client("bedrock-agentcore")
    row = []
    for v in ids.values():
        _, err = safe(dp.get_workload_access_token, workloadName=v["name"])
        row.append("token" if not err else err.split(":")[0])
    print(f"{team:<12}" + "".join(f"{c:<38}" for c in row))
