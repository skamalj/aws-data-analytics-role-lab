"""
What the rebalancing service does: assume its role, then invoke the rebalancer agent with SigV4 on behalf of a portfolio manager.

    python3 missions/S4-sigv4-rebalancing-path/scenarios/rebalance.py [--user pm-0042] [--as service|ops]
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "common"))
from sai import invoke_sigv4, mission, session  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default="pm-0042", help="portfolio manager the run is for (runtimeUserId); '' for none")
    ap.add_argument("--as", dest="who", default="service", choices=["service", "ops"])
    a = ap.parse_args()
    o = mission(os.path.join(HERE, ".."))
    role = o["service_role_arn"] if a.who == "service" else o["ops_console_role_arn"]
    ok, body = invoke_sigv4(session(role), o["runtime_arn"], {"action": "credential"}, user_id=a.user or None)
    print(json.dumps(body, indent=2) if ok else f"FAILED: {body}")
