"""
Run the self-hosted research agent on its EC2 host through Systems Manager Run Command and print what it reports.

    python3 missions/S2-self-hosted-workload-identity/scenarios/run_agent.py [--action whoami|credential]
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "common"))
from sai import mission, safe, session  # noqa: E402


def run(action="credential", quiet=False):
    o = mission(os.path.join(HERE, ".."))
    ssm = session().client("ssm")
    cmd = f"cd /opt/research-agent && AGENT_NAME=research-agent AWS_REGION={ssm.meta.region_name} python3 agent.py --self-hosted --action {action}"
    r, err = safe(ssm.send_command, InstanceIds=[o["instance_id"]], DocumentName="AWS-RunShellScript",
                  Parameters={"commands": [cmd]}, Comment="larchmont research agent")
    if err:
        return {"ssm_error": err}
    cid = r["Command"]["CommandId"]
    for _ in range(40):
        time.sleep(3)
        inv, err = safe(ssm.get_command_invocation, CommandId=cid, InstanceId=o["instance_id"])
        if inv and inv["Status"] not in ("Pending", "InProgress", "Delayed"):
            break
    if not inv:
        return {"ssm_error": err}
    out = inv.get("StandardOutputContent", "").strip().splitlines()
    try:
        res = json.loads(out[-1]) if out else {}
    except json.JSONDecodeError:
        res = {"raw": out[-1]}
    res["ssm_status"] = inv["Status"]
    if inv.get("StandardErrorContent"):
        res["stderr"] = inv["StandardErrorContent"][-400:]
    if not quiet:
        print(json.dumps(res, indent=2))
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--action", default="credential", choices=["whoami", "credential"])
    run(ap.parse_args().action)
