"""S1 check: each team mints workload access tokens for its own agents only, and can't re-tag an agent into its team."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "common"))
from sai import check, denied, finish, mission, safe, session  # noqa: E402

o = mission(os.path.join(HERE, ".."))
ids = o["workload_identities"]
sessions = {team: session(arn) for team, arn in o["ops_role_arns"].items()}
for team, s in sessions.items():
    dp = s.client("bedrock-agentcore")
    for key, v in ids.items():
        r, err = safe(dp.get_workload_access_token, workloadName=v["name"])
        if v["owner"] == team:
            check(f"{team} operators can mint a token for their own {key} agent", r is not None, err or "")
        else:
            check(f"{team} operators are denied a token for the {v['owner']} {key} agent", r is None and denied(err), err or "token issued!")

ctl = sessions["trading"].client("bedrock-agentcore-control")
advisor = ids["advisor"]
r, err = safe(ctl.tag_resource, resourceArn=advisor["arn"], tags={"abac-probe": "trading"})
if r is not None:                                    # it worked: clean up the probe tag
    safe(ctl.untag_resource, resourceArn=advisor["arn"], tagKeys=["abac-probe"])
check("trading operators cannot change the tags of another team's workload identity", r is None and denied(err), err or "tag_resource succeeded!")
tags = session().client("bedrock-agentcore-control").list_tags_for_resource(resourceArn=advisor["arn"]).get("tags", {})
check("the advisor agent is still owned by advisory", tags.get("team") == "advisory", f"tags: {tags}")
finish()
