"""
Part B check: start the AWS Labs PostgreSQL MCP server exactly as configured in awslabs/mcp.generated.json
(stdio, via uvx) and verify it is read-only, least-privileged and working.

    python3 missions/D4-mcp-diagnostics/awslabs/render.py
    python3 missions/D4-mcp-diagnostics/scenarios/check_awslabs.py
"""
import json
import os
import subprocess
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "common"))
from checks import check, finish  # noqa: E402
from dbsql import base_outputs  # noqa: E402

cfg_path = os.path.join(HERE, "..", "awslabs", "mcp.generated.json")
if not os.path.exists(cfg_path):
    sys.exit("run awslabs/render.py first")
srv = json.load(open(cfg_path))["mcpServers"]["riverbend-postgres"]
args, base = srv["args"], base_outputs()


def arg(name):
    return args[args.index(name) + 1] if name in args else None


# ---- static review of the configuration
check("connects through the RDS Data API (the cluster has no network path from laptops)", arg("--connection_method") == "RDS_API",
      f"--connection_method {arg('--connection_method')}")
check("uses the read-only diagnostics identity", arg("--secret_arn") == base["diag_secret_arn"],
      "admin secret!" if arg("--secret_arn") == base["admin_secret_arn"] else f"{arg('--secret_arn')}")
check("write queries are not enabled", "--allow_write_query" not in args)
check("the least-privilege guardrail is enforced", arg("--privilege_check") == "enforce", f"--privilege_check {arg('--privilege_check')}")

# ---- live test over stdio
proc = subprocess.Popen([srv["command"], *args], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                        text=True, env={**os.environ, **srv.get("env", {})})
stderr_lines = []
threading.Thread(target=lambda: stderr_lines.extend(proc.stderr), daemon=True).start()


def rpc(method, params=None, mid=[0]):
    mid[0] += 1
    proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": mid[0], "method": method, "params": params or {}}) + "\n")
    proc.stdin.flush()
    while True:
        line = proc.stdout.readline()
        if not line:
            raise RuntimeError("server exited: " + "".join(stderr_lines[-5:]))
        msg = json.loads(line)
        if msg.get("id") == mid[0]:
            return msg


try:
    rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "riverbend-check", "version": "1"}})
    proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
    proc.stdin.flush()
    common = {"connection_method": "RDS_API", "cluster_identifier": base["cluster_id"], "db_endpoint": "", "database": base["database"]}

    def query(sql):
        r = rpc("tools/call", {"name": "run_query", "arguments": {"sql": sql, **common}})
        res = r.get("result", {})
        text = "".join(c.get("text", "") for c in res.get("content", []))
        return (not res.get("isError") and "error" not in text.lower()[:200] and "error" not in r), text[:200]

    ok, text = query("SELECT count(*) AS orders FROM reporting.order_summary")
    check("server answers a read query", ok, text)
    ok, text = query("UPDATE commerce.audit_canary SET note = note WHERE id = 1")
    check("server refuses a write query", not ok, "the UPDATE was executed!" if ok else "")
except Exception as e:  # noqa: BLE001
    check("server starts and answers", False, f"{type(e).__name__}: {e}")
finally:
    proc.kill()
finish()
