"""Minimal MCP client for MCP servers hosted on AgentCore Runtime (SigV4 via InvokeAgentRuntime)."""
import json
import sys
import uuid

import boto3

from checks import mission_outputs


class Mcp:
    def __init__(self, mission_dir):
        self.o = mission_outputs(mission_dir)
        if "runtime_arn" not in self.o:
            sys.exit(f"mission not deployed ({mission_dir})")
        self.c = boto3.client("bedrock-agentcore", region_name=self.o["runtime_arn"].split(":")[3])
        self.session = f"mcp-{uuid.uuid4()}"
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
        return {t["name"]: t for t in self.rpc("tools/list")["tools"]}

    def call(self, name, args):
        res = self.rpc("tools/call", {"name": name, "arguments": args})
        text = "".join(c.get("text", "") for c in res.get("content", []))
        try:
            return json.loads(text), res.get("isError", False)
        except json.JSONDecodeError:
            return text, res.get("isError", False)
