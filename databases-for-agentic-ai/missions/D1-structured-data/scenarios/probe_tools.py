"""
Call the order-tools Lambda exactly as AgentCore Gateway does (tool name in the client context),
including one hostile input. Prints PASS/FAIL per check.
"""
import base64
import json
import os
import subprocess
import sys

import boto3

here = os.path.dirname(os.path.abspath(__file__))
out = {k: v["value"] for k, v in json.loads(subprocess.run(
    ["terraform", f"-chdir={here}/../terraform", "output", "-json"], capture_output=True, text=True).stdout).items()}
lam = boto3.client("lambda", region_name=out["runtime_arn"].split(":")[3])


def call(tool, args):
    ctx = base64.b64encode(json.dumps({"custom": {"bedrockAgentCoreToolName": f"orders___{tool}"}}).encode()).decode()
    r = lam.invoke(FunctionName=out["tools_function"], ClientContext=ctx, Payload=json.dumps(args).encode())
    return json.loads(r["Payload"].read())


checks = []
r = call("get_order", {"order_id": "O1003"})
print("get_order O1003 ->", json.dumps(r)[:300])
checks.append(("get_order works", r.get("order_id") == "O1003"))

r = call("category_activity", {"category": "Tents"})
print("category_activity Tents ->", json.dumps(r)[:300])
checks.append(("category_activity works", r.get("category") == "Tents"))

r = call("orders_for_customer", {"customer_id": "C00112"})
n = len(r.get("orders", []))
print(f"orders_for_customer C00112 -> {n} orders")
checks.append(("orders_for_customer works", n > 0 and "error" not in r))

evil = "C00112' OR customer_id LIKE 'C0001%"   # a customer id an attacker could type into the chat
r = call("orders_for_customer", {"customer_id": evil})
leaked = len(r.get("orders", [])) if isinstance(r.get("orders"), list) else 0
print(f"orders_for_customer {evil!r} -> {leaked} orders / {json.dumps(r)[:200]}")
checks.append(("hostile input returns no other customers' orders", leaked == 0 and n == 10))

for name, ok in checks:
    print(f"{'PASS' if ok else 'FAIL'}  {name}")
sys.exit(0 if all(ok for _, ok in checks) else 1)
