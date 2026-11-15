"""
Riverbend agent-memory inspector: an MCP server (AgentCore Runtime, protocol MCP) that lets
engineers inspect Trail Desk's conversation state in DynamoDB.

It reads checkpoints through langgraph-dynamodb-checkpoint itself, so state is decoded exactly
the way the agent wrote it. POST /mcp, JSON-RPC 2.0, stateless.
"""
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import boto3
from langgraph_dynamodb_checkpoint import DynamoDBSaver

os.environ.setdefault("AGENTSTATE_QUIET", "1")
REGION = os.environ.get("AWS_REGION", "us-west-2")
TABLE = os.environ["CHECKPOINT_TABLE"]
ddb = boto3.client("dynamodb", region_name=REGION)
_saver = None


def saver():
    global _saver
    if _saver is None:
        _saver = DynamoDBSaver(TABLE)
    return _saver


def cfg(thread_id):
    return {"configurable": {"thread_id": str(thread_id), "checkpoint_ns": ""}}


# ----------------------------------------------------------------- tools
def describe_memory_table(args):
    t = ddb.describe_table(TableName=TABLE)["Table"]
    ttl = ddb.describe_time_to_live(TableName=TABLE)["TimeToLiveDescription"]
    return {"table": TABLE, "keys": t["KeySchema"], "items": t.get("ItemCount"), "bytes": t.get("TableSizeBytes"),
            "ttl": ttl}


def list_threads(args):
    limit = int(args.get("limit", 20))
    threads, kwargs = set(), {"TableName": TABLE, "ProjectionExpression": "PK"}
    while len(threads) < limit:
        page = ddb.scan(**kwargs)
        threads.update(i["PK"]["S"] for i in page["Items"])
        if "LastEvaluatedKey" not in page:
            break
        kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]
    return {"threads": sorted(threads)[:limit]}


def get_conversation(args):
    tup = saver().get_tuple(cfg(args["thread_id"]))
    if not tup:
        return {"error": "no checkpoint for this thread"}
    msgs = tup.checkpoint.get("channel_values", {}).get("messages", [])
    return {"thread_id": args["thread_id"], "checkpoint_id": tup.config["configurable"]["checkpoint_id"],
            "step": tup.metadata.get("step"), "message_count": len(msgs),
            "messages": [{"type": m.type, "content": m.content} for m in msgs]}


def list_checkpoints(args):
    out = []
    for t in saver().list(cfg(args["thread_id"]), limit=int(args.get("limit", 10))):
        out.append({"checkpoint_id": t.config["configurable"]["checkpoint_id"], "step": t.metadata.get("step"),
                    "messages": len(t.checkpoint.get("channel_values", {}).get("messages", []))})
    return {"thread_id": args["thread_id"], "checkpoints": out}


def item_sizes(args):
    """Size of the stored items of a thread - spots threads approaching DynamoDB's 400 KB item limit."""
    r = ddb.query(TableName=TABLE, KeyConditionExpression="PK = :p",
                  ExpressionAttributeValues={":p": {"S": str(args["thread_id"])}})
    sizes = sorted((len(json.dumps(i, default=str)) for i in r["Items"]), reverse=True)
    return {"thread_id": args["thread_id"], "items": len(sizes), "largest_bytes_approx": sizes[:5]}


def delete_thread(args):
    saver().delete_thread(str(args["thread_id"]))
    return {"deleted": args["thread_id"]}


TOOLS = {
    "describe_memory_table": (describe_memory_table, "Key schema, size and TTL settings of the agent-memory table.", {}, []),
    "list_threads": (list_threads, "List conversation thread ids stored in agent memory.",
                     {"limit": {"type": "integer"}}, []),
    "get_conversation": (get_conversation, "Show the latest checkpointed conversation state of a thread.",
                         {"thread_id": {"type": "string"}}, ["thread_id"]),
    "list_checkpoints": (list_checkpoints, "List recent checkpoints of a thread (id, step, message count).",
                         {"thread_id": {"type": "string"}, "limit": {"type": "integer"}}, ["thread_id"]),
    "item_sizes": (item_sizes, "Approximate stored item sizes of a thread (400 KB item-limit check).",
                   {"thread_id": {"type": "string"}}, ["thread_id"]),
    "delete_thread": (delete_thread, "Delete a thread's state (cleanup during debugging).",
                      {"thread_id": {"type": "string"}}, ["thread_id"]),
}


# ----------------------------------------------------------------- MCP (JSON-RPC 2.0)
def handle_rpc(msg):
    mid, method, params = msg.get("id"), msg.get("method"), msg.get("params") or {}
    if mid is None:
        return None
    if method == "initialize":
        result = {"protocolVersion": params.get("protocolVersion", "2025-06-18"), "capabilities": {"tools": {}},
                  "serverInfo": {"name": "riverbend-agent-memory-inspector", "version": "1.0.0"}}
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
            out, err = TOOLS[name][0](args), False
        except Exception as e:
            out, err = {"error": f"{type(e).__name__}: {e}"}, True
        result = {"content": [{"type": "text", "text": json.dumps(out, default=str)}], "isError": err}
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
        self._send(200, {"status": "Healthy"}) if self.path.startswith("/ping") else self._send(405, {})

    def do_POST(self):
        if not self.path.startswith("/mcp"):
            return self._send(404, {})
        try:
            msg = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        except json.JSONDecodeError:
            return self._send(400, {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}})
        print(json.dumps({"rpc": msg.get("method"), "tool": (msg.get("params") or {}).get("name")}), flush=True)
        r = handle_rpc(msg)
        return self._send(200, r) if r is not None else self._send(202)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    print(f"agent-memory inspector on :8000/mcp (table {TABLE})", flush=True)
    ThreadingHTTPServer(("0.0.0.0", 8000), H).serve_forever()
