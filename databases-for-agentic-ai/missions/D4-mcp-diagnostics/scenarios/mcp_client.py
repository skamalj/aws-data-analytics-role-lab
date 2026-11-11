"""
Minimal MCP client for the diagnostics server on AgentCore Runtime (SigV4 via InvokeAgentRuntime).

    python3 missions/D4-mcp-diagnostics/scenarios/mcp_client.py tools
    python3 missions/D4-mcp-diagnostics/scenarios/mcp_client.py call describe_table '{"table_name": "commerce.orders"}'
"""
import json
import os
import subprocess
import sys
import uuid

import boto3

HERE = os.path.dirname(os.path.abspath(__file__))


def outputs():
    r = subprocess.run(["terraform", f"-chdir={HERE}/../terraform", "output", "-json"], capture_output=True, text=True)
    return {k: v["value"] for k, v in json.loads(r.stdout or "{}").items()}


class Mcp:
    def __init__(self):
        self.o = outputs()
        if "runtime_arn" not in self.o:
            sys.exit("D4 not deployed: ./scripts/deploy.sh D4")
        self.c = boto3.client("bedrock-agentcore", region_name=self.o["runtime_arn"].split(":")[3])
        self.session = f"diag-{uuid.uuid4()}"
        self.rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                "clientInfo": {"name": "riverbend-audit", "version": "1"}})

    def rpc(self, method, params=None):
        body = {"jsonrpc": "2.0", "id": uuid.uuid4().hex[:8], "method": method, "params": params or {}}
        r = self.c.invoke_agent_runtime(agentRuntimeArn=self.o["runtime_arn"], qualifier="DEFAULT",
                                        runtimeSessionId=self.session, contentType="application/json",
                                        accept="application/json, text/event-stream", payload=json.dumps(body).encode())
        text = r["response"].read().decode()
        if not text.lstrip().startswith(("{", "[")):
            text = [l[5:] for l in text.splitlines() if l.startswith("data:")][-1]
        msg = json.loads(text)
        if "error" in msg:
            raise RuntimeError(msg["error"])
        return msg["result"]

    def tools(self):
        return self.rpc("tools/list")["tools"]

    def call(self, name, args):
        res = self.rpc("tools/call", {"name": name, "arguments": args})
        text = "".join(c.get("text", "") for c in res.get("content", []))
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = text
        return data, res.get("isError", False)


if __name__ == "__main__":
    m = Mcp()
    if sys.argv[1] == "tools":
        for t in m.tools():
            print(f"{t['name']:16} {json.dumps(t['inputSchema'].get('properties', {}))}\n{'':16} {t['description']}")
    else:
        data, err = m.call(sys.argv[2], json.loads(sys.argv[3] if len(sys.argv) > 3 else "{}"))
        print(("ERROR " if err else "") + json.dumps(data, indent=2, default=str)[:6000])
