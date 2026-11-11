"""
Riverbend order tools for agents (AgentCore Gateway Lambda target).
Reads the shared Aurora PostgreSQL cluster through the RDS Data API.

Tools: get_order(order_id) | orders_for_customer(customer_id) | category_activity(category)
"""
import json
import os

import boto3

rds = boto3.client("rds-data")
DB = {"resourceArn": os.environ["CLUSTER_ARN"], "secretArn": os.environ["DB_SECRET_ARN"],
      "database": os.environ["DB_NAME"]}


def query(sql, params=None):
    r = rds.execute_statement(sql=sql, parameters=params or [], formatRecordsAs="JSON", **DB)
    return json.loads(r.get("formattedRecords") or "[]")


def get_order(args):
    rows = query("SELECT order_id, customer_id, order_date, status, channel, total, items "
                 "FROM reporting.order_summary WHERE order_id = :id",
                 [{"name": "id", "value": {"stringValue": str(args.get("order_id", ""))}}])
    return rows[0] if rows else {"error": "order not found"}


def orders_for_customer(args):
    cid = args.get("customer_id", "")
    rows = query("SELECT order_id, order_date, status, total, items FROM reporting.order_summary "
                 f"WHERE customer_id = '{cid}' ORDER BY order_date DESC")
    return {"customer_id": cid, "orders": rows}


def category_activity(args):
    rows = query("SELECT category, order_line_count, units_sold, latest_activity "
                 "FROM reporting.category_activity WHERE category = :c",
                 [{"name": "c", "value": {"stringValue": str(args.get("category", ""))}}])
    return rows[0] if rows else {"error": "unknown category"}


HANDLERS = {"get_order": get_order, "orders_for_customer": orders_for_customer,
            "category_activity": category_activity}


def handler(event, context):
    tool = context.client_context.custom["bedrockAgentCoreToolName"].split("___", 1)[-1]
    print(json.dumps({"tool": tool, "arguments": event}))
    try:
        return HANDLERS[tool](event)
    except Exception as e:
        print(f"ERROR {type(e).__name__}: {e}")
        return {"error": f"{type(e).__name__}: {e}"}
