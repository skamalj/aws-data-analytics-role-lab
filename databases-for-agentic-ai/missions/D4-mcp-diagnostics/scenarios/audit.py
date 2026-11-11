"""Security review of the diagnostics MCP server. Every check must PASS."""
import json
import os
import sys

import boto3

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "common"))
from dbsql import base_outputs  # noqa: E402
from mcp_client import Mcp  # noqa: E402

m = Mcp()
base = base_outputs()
region = m.o["runtime_arn"].split(":")[3]
results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  -- {detail}" if detail else ""))


tools = {t["name"]: t for t in m.tools()}
check("server lists its tools", bool(tools), ", ".join(tools))

# Call it the way any MCP client (or coding agent) would: with the argument name the server ADVERTISES.
arg = (tools["describe_table"]["inputSchema"].get("required") or ["table_name"])[0]
data, err = m.call("describe_table", {arg: "commerce.orders"})
check("describe_table works", not err and bool(data.get("columns")), str(data)[:120] if err else "")

data, err = m.call("sample_rows", {"table_name": "commerce.customers", "limit": 100000})
rows = data.get("rows", []) if isinstance(data, dict) else []
blob = json.dumps(data)
check("sample_rows is capped (<= 20 rows)", not err and 0 < len(rows) <= 20, f"{len(rows)} rows returned")
check("sample_rows redacts personal data", "@example.com" not in blob and "+1-555-" not in blob)

data, err = m.call("ddb_sample", {"table_name": m.o["sessions_table"], "limit": 100000})
items = data.get("items", []) if isinstance(data, dict) else []
check("ddb_sample is capped and redacted", not err and 0 < len(items) <= 20 and "@example.com" not in json.dumps(data),
      f"{len(items)} items")

if "run_sql" in tools:
    data, err = m.call("run_sql", {"sql": "UPDATE commerce.audit_canary SET note = note WHERE id = 1"})
    check("no tool can modify data", err, "run_sql executed an UPDATE" if not err else "")
else:
    check("no tool can modify data", True, "no free-form SQL tool exposed")

env = boto3.client("bedrock-agentcore-control", region_name=region).get_agent_runtime(
    agentRuntimeId=m.o["runtime_id"])["environmentVariables"]
check("server uses the read-only database identity", env.get("DB_SECRET_ARN") == base["diag_secret_arn"],
      "uses the ADMIN secret" if env.get("DB_SECRET_ARN") == base["admin_secret_arn"] else "")

iam = boto3.client("iam")
table_arn = f"arn:aws:dynamodb:{region}:{base['account_id']}:table/{m.o['sessions_table']}"
def allowed_actions(actions, resource):
    res = iam.simulate_principal_policy(PolicySourceArn=m.o["runtime_role_arn"], ActionNames=actions,
                                        ResourceArns=[resource])["EvaluationResults"]
    return [r["EvalActionName"] for r in res if r["EvalDecision"] == "allowed"]


too_much = allowed_actions(["dynamodb:PutItem", "dynamodb:DeleteItem", "dynamodb:DeleteTable"], table_arn) + \
          allowed_actions(["secretsmanager:GetSecretValue"], base["admin_secret_arn"])
check("role cannot write DynamoDB or read the admin secret", not too_much, "; ".join(too_much))

print(f"\n{sum(results)}/{len(results)} checks passed")
sys.exit(0 if all(results) else 1)
