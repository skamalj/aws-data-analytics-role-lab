"""Order lookup tool for Trail Desk (AgentCore Gateway Lambda target, RDS Data API, app identity)."""
import json
import os
import re

import boto3

rds = boto3.client("rds-data")
DB = {"resourceArn": os.environ["CLUSTER_ARN"], "secretArn": os.environ["DB_SECRET_ARN"], "database": os.environ["DB_NAME"]}
ORDER_ID = re.compile(r"^O\d{4,7}$")


def get_order(args):
    oid = str(args.get("order_id", "")).upper()
    if not ORDER_ID.fullmatch(oid):
        return {"error": "order_id must look like O1003"}
    r = rds.execute_statement(
        sql="SELECT order_id, order_date, status, channel, total, items FROM reporting.order_summary WHERE order_id = :id",
        parameters=[{"name": "id", "value": {"stringValue": oid}}], formatRecordsAs="JSON", **DB)
    rows = json.loads(r.get("formattedRecords") or "[]")
    return rows[0] if rows else {"error": "order not found"}


def handler(event, context):
    tool = context.client_context.custom["bedrockAgentCoreToolName"].split("___", 1)[-1]
    print(json.dumps({"tool": tool, "arguments": event}))
    if tool != "get_order":
        return {"error": f"unknown tool {tool}"}
    try:
        return get_order(event)
    except Exception as e:
        print(f"ERROR {type(e).__name__}: {e}")
        return {"error": "order service unavailable, try again shortly"}
