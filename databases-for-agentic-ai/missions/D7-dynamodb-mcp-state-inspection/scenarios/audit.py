"""Security and usefulness review of the agent-memory inspector (MCP). Every check must PASS."""
import json
import os
import sys

import boto3

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "common"))
from checks import check, finish, safe  # noqa: E402
from mcp_client import Mcp  # noqa: E402

m = Mcp(os.path.join(HERE, ".."))
region, table = m.o["region"], m.o["memory_table"]
ddb = boto3.client("dynamodb", region_name=region)
tools = m.tools()
check("server lists its tools", bool(tools), ", ".join(tools))

data, err = m.call("describe_memory_table", {})
check("inspector reads the agent's real memory table", not err and data.get("table") == table,
      f"inspects '{data.get('table') if isinstance(data, dict) else data}', the agent writes '{table}'")

data, err = m.call("list_threads", {"limit": 50})
threads = data.get("threads", []) if isinstance(data, dict) else []
check("list_threads shows the seeded conversations (5)", len(threads) >= 5, f"{len(threads)} threads")

data, err = m.call("get_conversation", {"thread_id": "sizing-C00042-s1"})
blob = json.dumps(data)
msgs = data.get("messages", []) if isinstance(data, dict) else []
check("get_conversation is bounded (<= 20 messages, <= 20 KB)", not err and 0 < len(msgs) <= 20 and len(blob) <= 20_000,
      f"{len(msgs)} messages, {len(blob):,} bytes")
data, err = m.call("get_conversation", {"thread_id": "support-C00112-c1"})
blob = json.dumps(data)
check("get_conversation redacts e-mail addresses and phone numbers",
      not err and "dana.k@example.com" not in blob and "+1-555-0177" not in blob and "messages" in blob)

write_tools = [t for t in tools if any(w in t for w in ("delete", "put", "update", "prune", "copy"))]
check("no tool can change agent memory", not write_tools, ", ".join(write_tools))

iam = boto3.client("iam")
arn = f"arn:aws:dynamodb:{region}:{boto3.client('sts').get_caller_identity()['Account']}:table/{table}"
res = iam.simulate_principal_policy(PolicySourceArn=m.o["runtime_role_arn"], ResourceArns=[arn],
                                    ActionNames=["dynamodb:PutItem", "dynamodb:DeleteItem", "dynamodb:BatchWriteItem",
                                                 "dynamodb:UpdateItem", "dynamodb:CreateTable", "dynamodb:DeleteTable"])
allowed = [r["EvalActionName"] for r in res["EvaluationResults"] if r["EvalDecision"] == "allowed"]
check("inspector role is read-only on the memory table", not allowed, ", ".join(allowed))

stray = [t for t in ddb.list_tables()["TableNames"] if t.startswith("riverbend-d7-") and t != table]
check("no stray tables were created by the inspector", not stray, ", ".join(stray))
finish()
