"""S2 check: the self-hosted research agent has a workload identity, is reachable through SSM, and gets its API key via the token vault."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "common"))
sys.path.insert(0, HERE)
from run_agent import run  # noqa: E402
from sai import check, finish, mission, safe, session  # noqa: E402

o = mission(os.path.join(HERE, ".."))
s = session()
wi, err = safe(s.client("bedrock-agentcore-control").get_workload_identity, name=o["workload_name"])
check(f"workload identity {o['workload_name']} exists", wi is not None, err or "")
tags = {}
if wi:
    tags = s.client("bedrock-agentcore-control").list_tags_for_resource(resourceArn=wi["workloadIdentityArn"]).get("tags", {})
check("the workload identity is tagged team = research (fleet ABAC, see S1)", tags.get("team") == "research", f"tags: {tags}")

info = s.client("ssm").describe_instance_information(Filters=[{"Key": "InstanceIds", "Values": [o["instance_id"]]}])["InstanceInformationList"]
check("the agent host is a managed instance in Systems Manager (no SSH needed)", bool(info) and info[0].get("PingStatus") == "Online",
      f"{info[0].get('PingStatus') if info else 'not registered - check the instance profile, then wait ~5 minutes'}")
attached = [p["PolicyName"] for p in s.client("iam").list_attached_role_policies(RoleName=o["host_role_name"])["AttachedPolicies"]]
check("the host role grants no administrator or power-user access", not {"AdministratorAccess", "PowerUserAccess"} & set(attached), f"attached: {attached}")

res = run("credential", quiet=True) if info else {"ssm_error": "host not managed"}
print(f"  agent said: {res}")
check("the agent ran through SSM Run Command", res.get("ssm_status") == "Success", res.get("ssm_error") or res.get("stderr", ""))
check("the agent obtained a workload access token for itself", res.get("workload_token") is True, res.get("message", ""))
check("the agent obtained the Market Data API key from the token vault", res.get("credential") == "obtained",
      f"{res.get('error', '')} {res.get('message', '')}".strip())
finish()
