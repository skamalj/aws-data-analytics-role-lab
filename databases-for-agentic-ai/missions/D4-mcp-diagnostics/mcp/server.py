"""
Riverbend developer-diagnostics MCP server (AgentCore Runtime, protocol MCP).

Lets engineers - and their coding agents - inspect the data services behind Trail Desk:
PostgreSQL schema and sample rows (RDS Data API) and DynamoDB table metadata and sample items.

MCP over streamable HTTP, stateless: POST /mcp with JSON-RPC 2.0 (initialize, tools/list, tools/call, ping).
"""
import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import boto3

REGION = os.environ.get("AWS_REGION", "us-west-2")
rds = boto3.client("rds-data", region_name=REGION)
ddb = boto3.client("dynamodb", region_name=REGION)
DB = {"resourceArn": os.environ["CLUSTER_ARN"], "secretArn": os.environ["DB_SECRET_ARN"], "database": os.environ["DB_NAME"]}
DDB_TABLES = [t for t in os.environ.get("DDB_TABLES", "").split(",") if t]
IDENT = re.compile(r"^[a-z_][a-z0-9_]*\.[a-z_][a-z0-9_]*$")    # schema.table


def sql(statement, params=None):
    r = rds.execute_statement(sql=statement, parameters=params or [], formatRecordsAs="JSON", **DB)
    return json.loads(r.get("formattedRecords") or "[]") if "formattedRecords" in r else {"rows_affected": r.get("numberOfRecordsUpdated")}


def qualified(name):
    name = str(name).lower()
    if not IDENT.fullmatch(name):
        raise ValueError("table must be written as schema.table, e.g. commerce.orders")
    return name


# ----------------------------------------------------------------- tools
def list_tables(args):
    pg = sql("SELECT table_schema || '.' || table_name AS name, table_type FROM information_schema.tables "
             "WHERE table_schema IN ('commerce', 'reporting', 'bedrock_kb') ORDER BY 1")
    return {"postgres": pg, "dynamodb": DDB_TABLES}


def describe_table(args):
    schema, table = qualified(args["table_name"]).split(".")
    cols = sql("SELECT column_name, data_type, is_nullable FROM information_schema.columns "
               "WHERE table_schema = :s AND table_name = :t ORDER BY ordinal_position",
               [{"name": "s", "value": {"stringValue": schema}}, {"name": "t", "value": {"stringValue": table}}])
    return {"table": f"{schema}.{table}", "columns": cols} if cols else {"error": "no such table (or no access)"}


def sample_rows(args):
    name = qualified(args["table_name"])
    limit = int(args.get("limit", 1000))
    return {"table": name, "rows": sql(f"SELECT * FROM {name} LIMIT {limit}")}


def run_sql(args):
    return sql(str(args["sql"]))


def ddb_describe(args):
    t = ddb.describe_table(TableName=args["table_name"])["Table"]
    return {k: t.get(k) for k in ("TableName", "KeySchema", "AttributeDefinitions", "ItemCount", "TableSizeBytes",
                                  "BillingModeSummary", "TableStatus")}


def ddb_sample(args):
    items = ddb.scan(TableName=args["table_name"], Limit=int(args.get("limit", 1000)))["Items"]
    return {"table": args["table_name"], "items": [{k: list(v.values())[0] for k, v in i.items()} for i in items]}


TOOLS = {
    "list_tables": (list_tables, "List PostgreSQL tables/views (commerce, reporting, bedrock_kb) and DynamoDB tables.", {}, []),
    "describe_table": (describe_table, "Show the columns of a PostgreSQL table or view.",
                       {"table": {"type": "string", "description": "schema.table, e.g. commerce.orders"}}, ["table"]),
    "sample_rows": (sample_rows, "Return sample rows from a PostgreSQL table or view.",
                    {"table_name": {"type": "string", "description": "schema.table"},
                     "limit": {"type": "integer", "description": "number of rows"}}, ["table_name"]),
    "run_sql": (run_sql, "Run a SQL statement for troubleshooting.",
                {"sql": {"type": "string"}}, ["sql"]),
    "ddb_describe": (ddb_describe, "Describe a DynamoDB table (keys, size, item count).",
                     {"table_name": {"type": "string"}}, ["table_name"]),
    "ddb_sample": (ddb_sample, "Return sample items from a DynamoDB table.",
                   {"table_name": {"type": "string"}, "limit": {"type": "integer"}}, ["table_name"]),
}


# ----------------------------------------------------------------- MCP (JSON-RPC 2.0)
def handle_rpc(msg):
    mid, method, params = msg.get("id"), msg.get("method"), msg.get("params") or {}
    if mid is None:                       # notification (e.g. notifications/initialized)
        return None
    if method == "initialize":
        result = {"protocolVersion": params.get("protocolVersion", "2025-06-18"),
                  "capabilities": {"tools": {"listChanged": False}},
                  "serverInfo": {"name": "riverbend-db-diagnostics", "version": "1.0.0"}}
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": [{"name": n, "description": d, "inputSchema": {"type": "object", "properties": p, "required": r}}
                            for n, (_, d, p, r) in TOOLS.items()]}
    elif method == "tools/call":
        name, args = params.get("name"), params.get("arguments") or {}
        if name not in TOOLS:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32602, "message": f"unknown tool {name}"}}
        try:
            out, is_error = TOOLS[name][0](args), False
        except Exception as e:
            out, is_error = {"error": f"{type(e).__name__}: {e}"}, True
        result = {"content": [{"type": "text", "text": json.dumps(out, default=str)}], "isError": is_error}
    else:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"method not found: {method}"}}
    return {"jsonrpc": "2.0", "id": mid, "result": result}


class H(BaseHTTPRequestHandler):
    def _send(self, code, obj=None):
        body = json.dumps(obj).encode() if obj is not None else b""
        self.send_response(code)
        if obj is not None:
            self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._send(200, {"status": "Healthy"}) if self.path.startswith("/ping") else self._send(405, {"error": "use POST"})

    def do_POST(self):
        if not self.path.startswith("/mcp"):
            return self._send(404, {"error": "not found"})
        try:
            msg = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        except json.JSONDecodeError:
            return self._send(400, {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}})
        print(json.dumps({"rpc": msg.get("method") if isinstance(msg, dict) else "batch",
                          "tool": (msg.get("params") or {}).get("name") if isinstance(msg, dict) else None}), flush=True)
        if isinstance(msg, list):
            out = [r for r in (handle_rpc(m) for m in msg) if r is not None]
            return self._send(200, out) if out else self._send(202)
        r = handle_rpc(msg)
        return self._send(200, r) if r is not None else self._send(202)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    print("riverbend-db-diagnostics MCP server on :8000/mcp", flush=True)
    ThreadingHTTPServer(("0.0.0.0", 8000), H).serve_forever()
