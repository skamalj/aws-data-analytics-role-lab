"""
Trail Desk product tools (AgentCore Gateway Lambda target) over catalog.products (~200k rows).
Each response includes db_ms, and every call emits a CloudWatch metric (Embedded Metric Format):
namespace Riverbend/ProductSearch, metric QueryMs, dimension Tool.
"""
import json
import os
import time

import boto3

rds = boto3.client("rds-data")
DB = {"resourceArn": os.environ["CLUSTER_ARN"], "secretArn": os.environ["DB_SECRET_ARN"], "database": os.environ["DB_NAME"]}


def query(sql, params=None):
    r = rds.execute_statement(sql=sql, parameters=params or [], formatRecordsAs="JSON", **DB)
    return json.loads(r.get("formattedRecords") or "[]")


def p(name, value):
    if isinstance(value, (int, float)):
        return {"name": name, "value": {"doubleValue": float(value)}}
    return {"name": name, "value": {"stringValue": str(value)}}


def search_products(args):
    term = str(args.get("query", "")).strip()
    limit = int(args.get("limit", 10))
    rows = query("SELECT * FROM catalog.products WHERE name ILIKE :pat OR description ILIKE :pat",
                 [p("pat", f"%{term}%")])
    if args.get("category"):
        rows = [r for r in rows if r["category"] == args["category"]]
    if args.get("max_price"):
        rows = [r for r in rows if float(r["price"]) <= float(args["max_price"])]
    rows = [r for r in rows if r["in_stock"]]
    rows.sort(key=lambda r: float(r["rating"]), reverse=True)
    return [{k: r[k] for k in ("product_id", "name", "category", "price", "rating")} for r in rows[:limit]]


def browse_category(args):
    rows = query("SELECT product_id, name, price, rating FROM catalog.products "
                 "WHERE category = :c AND price <= :maxp AND in_stock ORDER BY price LIMIT 20",
                 [p("c", args.get("category", "")), p("maxp", float(args.get("max_price", 100000)))])
    return rows


def similar_products(args):
    return query("SELECT product_id, name, price FROM catalog.products "
                 "WHERE product_id <> :id "
                 "ORDER BY embedding <=> (SELECT embedding FROM catalog.products WHERE product_id = :id) LIMIT 5",
                 [p("id", args.get("product_id", ""))])


TOOLS = {"search_products": search_products, "browse_category": browse_category, "similar_products": similar_products}


def handler(event, context):
    tool = context.client_context.custom["bedrockAgentCoreToolName"].split("___", 1)[-1]
    if tool not in TOOLS:
        return {"error": f"unknown tool {tool}"}
    t0 = time.perf_counter()
    try:
        result, error = TOOLS[tool](event), None
    except Exception as e:
        result, error = None, f"{type(e).__name__}: {str(e)[:300]}"
    ms = round((time.perf_counter() - t0) * 1000, 1)
    print(json.dumps({"_aws": {"Timestamp": int(time.time() * 1000), "CloudWatchMetrics": [{
        "Namespace": "Riverbend/ProductSearch", "Dimensions": [["Tool"]],
        "Metrics": [{"Name": "QueryMs", "Unit": "Milliseconds"}]}]},
        "Tool": tool, "QueryMs": ms, "error": error, "arguments": event}))
    return {"error": error, "db_ms": ms} if error else {"results": result, "db_ms": ms}
