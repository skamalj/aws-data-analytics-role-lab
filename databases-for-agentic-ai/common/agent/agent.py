"""
Riverbend "Trail Desk" agent: a plain-Python agent for Amazon Bedrock AgentCore Runtime.

Runtime contract: HTTP on 0.0.0.0:8080, POST /invocations (JSON in, JSON out), GET /ping.
Features switch on with environment variables, so every mission deploys the same code:

  MODEL_ID            Bedrock model or inference profile used through the Converse API (required)
  SYSTEM_PROMPT       Persona / instructions
  INTERNAL_CONTEXT    Extra (sensitive) context the agent is given, e.g. internal notes  [mission 6]
  GATEWAY_URL         AgentCore Gateway MCP endpoint; tools are listed and called over MCP,
                      requests SigV4-signed with the runtime role                        [mission 2]
  KB_ID               Bedrock Knowledge Base id, exposed as the tool search_manuals       [mission 3]
  MEMORY_ID           AgentCore Memory id; short-term events + long-term records          [mission 4]
  MEMORY_NAMESPACE    Namespace template to read long-term records from, e.g. /users/{actorId}/preferences
  STORE_TABLE         DynamoDB table with store information, exposed as the tool store_info  [mission 5]
  GUARDRAIL_ID / GUARDRAIL_VERSION   Bedrock Guardrail applied to every model call       [mission 6]

Request body : {"prompt": "...", "actor_id": "optional user id"}
Response body: {"answer": "...", "tools_used": [...], "trace": [...]}  or  {"error": "...", "trace": [...]}
"""
import json
import os
import traceback
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.config import Config

REGION = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION", "us-west-2")
# Short timeouts and no retries: a network problem shows up in seconds as a clear error.
CFG = Config(connect_timeout=5, read_timeout=30, retries={"max_attempts": 1, "mode": "standard"})
session = boto3.Session(region_name=REGION)
bedrock = session.client("bedrock-runtime", config=CFG)

DEFAULT_PROMPT = ("You are Trail Desk, the customer assistant of Riverbend Outfitters, an outdoor-gear "
                  "retailer. Be concise. Use the tools you are given whenever they can answer the question; "
                  "never invent order numbers, stock levels or policies.")


def env(name):
    v = os.environ.get(name, "").strip()
    return v or None


# --------------------------------------------------------------------------- tools
class Tools:
    def __init__(self, trace):
        self.trace = trace
        self.specs, self.handlers = [], {}
        if env("GATEWAY_URL"):
            self._load_gateway_tools()
        if env("KB_ID"):
            self._add("search_manuals",
                      "Search Riverbend product manuals, care guides and warranty/returns policies. "
                      "Use for any question about how a product works, care, warranty or policy.",
                      {"query": {"type": "string", "description": "what to look up"}}, ["query"],
                      self._search_manuals)
        if env("STORE_TABLE"):
            self._add("store_info",
                      "Look up a Riverbend store's address and opening hours by store id (S01..S20).",
                      {"store_id": {"type": "string", "description": "store id, e.g. S07"}}, ["store_id"],
                      self._store_info)

    def _add(self, name, description, props, required, fn):
        self.specs.append({"toolSpec": {"name": name, "description": description,
                                        "inputSchema": {"json": {"type": "object", "properties": props,
                                                                 "required": required}}}})
        self.handlers[name] = fn

    # ---- AgentCore Gateway (MCP over streamable HTTP, SigV4 / AWS_IAM authorizer)
    def _mcp(self, method, params=None):
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}).encode()
        url = env("GATEWAY_URL")
        req = AWSRequest(method="POST", url=url, data=body,
                         headers={"Content-Type": "application/json",
                                  "Accept": "application/json, text/event-stream"})
        SigV4Auth(session.get_credentials().get_frozen_credentials(), "bedrock-agentcore", REGION).add_auth(req)
        r = urllib.request.Request(url, data=body, method="POST", headers=dict(req.headers.items()))
        with urllib.request.urlopen(r, timeout=30) as resp:
            text = resp.read().decode()
        if text.lstrip().startswith("{"):
            msg = json.loads(text)
        else:  # server-sent events: take the last data: line
            msg = json.loads([l[5:] for l in text.splitlines() if l.startswith("data:")][-1])
        if "error" in msg:
            raise RuntimeError(f"MCP {method} error: {msg['error']}")
        return msg["result"]

    def _load_gateway_tools(self):
        tools = self._mcp("tools/list").get("tools", [])
        self.trace.append({"gateway_tools": [t["name"] for t in tools]})
        for t in tools:
            schema = t.get("inputSchema") or {"type": "object", "properties": {}}
            self.specs.append({"toolSpec": {"name": t["name"], "description": t.get("description") or t["name"],
                                            "inputSchema": {"json": schema}}})
            self.handlers[t["name"]] = (lambda args, n=t["name"]: self._call_gateway(n, args))

    def _call_gateway(self, name, args):
        res = self._mcp("tools/call", {"name": name, "arguments": args})
        text = "\n".join(c.get("text", "") for c in res.get("content", []))
        if res.get("isError"):
            raise RuntimeError(f"tool {name} failed: {text}")
        return text

    # ---- Knowledge Base
    def _search_manuals(self, args):
        kb = session.client("bedrock-agent-runtime", config=CFG)
        out = kb.retrieve(knowledgeBaseId=env("KB_ID"), retrievalQuery={"text": args["query"]},
                          retrievalConfiguration={"vectorSearchConfiguration": {"numberOfResults": 4}})
        hits = [{"text": r["content"]["text"],
                 "source": r.get("location", {}).get("s3Location", {}).get("uri"),
                 "score": round(r.get("score", 0), 3)} for r in out["retrievalResults"]]
        return json.dumps(hits) if hits else "No matching passages found."

    # ---- DynamoDB
    def _store_info(self, args):
        ddb = session.client("dynamodb", config=CFG)
        item = ddb.get_item(TableName=env("STORE_TABLE"), Key={"store_id": {"S": args["store_id"].upper()}}).get("Item")
        return json.dumps({k: list(v.values())[0] for k, v in item.items()}) if item else "No such store."

    def call(self, name, args):
        if name not in self.handlers:
            raise RuntimeError(f"model asked for unknown tool {name}")
        return self.handlers[name](args)


# --------------------------------------------------------------------------- memory
class Memory:
    def __init__(self, actor_id, session_id, trace):
        self.id, self.actor, self.session, self.trace = env("MEMORY_ID"), actor_id, session_id, trace
        self.client = session.client("bedrock-agentcore", config=CFG) if self.id else None

    def context(self, prompt):
        if not self.client:
            return ""
        parts = []
        ns_tpl = env("MEMORY_NAMESPACE")
        if ns_tpl:
            ns = ns_tpl.replace("{actorId}", self.actor).replace("{sessionId}", self.session)
            recs = self.client.retrieve_memory_records(
                memoryId=self.id, namespace=ns, searchCriteria={"searchQuery": prompt, "topK": 5})
            facts = [r["content"]["text"] for r in recs.get("memoryRecordSummaries", [])]
            self.trace.append({"memory_namespace": ns, "long_term_records": len(facts)})
            if facts:
                parts.append("What you remember about this customer from earlier conversations:\n- "
                             + "\n- ".join(facts))
        events = self.client.list_events(memoryId=self.id, actorId=self.actor, sessionId=self.session,
                                         includePayloads=True, maxResults=10).get("events", [])
        turns = []
        for e in sorted(events, key=lambda e: e["eventTimestamp"]):
            for p in e.get("payload", []):
                c = p.get("conversational")
                if c:
                    turns.append(f"{c['role']}: {c['content']['text']}")
        self.trace.append({"short_term_turns": len(turns)})
        if turns:
            parts.append("Earlier in this conversation:\n" + "\n".join(turns[-10:]))
        return "\n\n".join(parts)

    def save(self, prompt, answer):
        if self.client:
            self.client.create_event(
                memoryId=self.id, actorId=self.actor, sessionId=self.session,
                eventTimestamp=datetime.now(timezone.utc),
                payload=[{"conversational": {"content": {"text": prompt}, "role": "USER"}},
                         {"conversational": {"content": {"text": answer}, "role": "ASSISTANT"}}])


# --------------------------------------------------------------------------- agent loop
def run(payload, session_id):
    trace = []
    prompt = str(payload.get("prompt", "")).strip()
    if not prompt:
        return {"error": "payload needs a 'prompt'"}
    actor = str(payload.get("actor_id") or "anonymous")
    try:
        memory = Memory(actor, session_id, trace)
        tools = Tools(trace)
        system = [{"text": env("SYSTEM_PROMPT") or DEFAULT_PROMPT}]
        if env("INTERNAL_CONTEXT"):
            system.append({"text": "Internal context (for staff use):\n" + env("INTERNAL_CONTEXT")})
        remembered = memory.context(prompt)
        if remembered:
            system.append({"text": remembered})

        kwargs = {"modelId": env("MODEL_ID"), "system": system,
                  "inferenceConfig": {"maxTokens": 700, "temperature": 0.2}}
        if tools.specs:
            kwargs["toolConfig"] = {"tools": tools.specs}
        if env("GUARDRAIL_ID"):
            kwargs["guardrailConfig"] = {"guardrailIdentifier": env("GUARDRAIL_ID"),
                                         "guardrailVersion": env("GUARDRAIL_VERSION") or "DRAFT",
                                         "trace": "enabled"}
        messages = [{"role": "user", "content": [{"text": prompt}]}]
        used = []
        for _ in range(6):
            out = bedrock.converse(messages=messages, **kwargs)
            msg = out["output"]["message"]
            messages.append(msg)
            if out.get("stopReason") == "guardrail_intervened":
                trace.append({"guardrail": "intervened"})
            calls = [c["toolUse"] for c in msg["content"] if "toolUse" in c]
            if not calls:
                break
            results = []
            for c in calls:
                used.append({"tool": c["name"], "input": c["input"]})
                try:
                    res, status = tools.call(c["name"], c["input"]), "success"
                except Exception as e:  # surface tool errors to the model and to the caller
                    res, status = f"{type(e).__name__}: {e}", "error"
                    trace.append({"tool_error": c["name"], "detail": res[:500]})
                results.append({"toolResult": {"toolUseId": c["toolUseId"], "status": status,
                                               "content": [{"text": str(res)[:6000]}]}})
            messages.append({"role": "user", "content": results})
        answer = "".join(c.get("text", "") for c in messages[-1]["content"]) if messages[-1]["role"] == "assistant" else ""
        memory.save(prompt, answer)
        return {"answer": answer, "tools_used": used, "trace": trace}
    except Exception as e:
        print(traceback.format_exc(), flush=True)
        return {"error": f"{type(e).__name__}: {e}", "trace": trace}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        body = json.dumps(obj, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/ping"):
            self._send(200, {"status": "Healthy"})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        if not self.path.startswith("/invocations"):
            return self._send(404, {"error": "not found"})
        try:
            payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        except json.JSONDecodeError:
            return self._send(400, {"error": "body must be JSON"})
        sid = self.headers.get("X-Amzn-Bedrock-AgentCore-Runtime-Session-Id", "local-session")
        result = run(payload, sid)
        print(json.dumps({"session": sid, "prompt": payload.get("prompt"), "result": result}, default=str)[:4000],
              flush=True)
        self._send(200, result)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    print(f"Trail Desk agent listening on :8080 (region {REGION})", flush=True)
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
