"""
Small LangGraph toolkit for the Trail Desk agent on AgentCore Runtime.

  * A two-node ReAct graph (model -> tools -> model ...) over MessagesState, calling Amazon
    Bedrock through the Converse API (boto3 only, no extra LLM SDKs).
  * Tools are plain Python functions with a JSON schema; they receive (args, ctx) where ctx is
    the trusted per-request context the *application* supplies (never the model).
  * serve(handler) implements the AgentCore Runtime HTTP contract (POST /invocations, GET /ping).

The checkpointer is chosen by each mission's app.py and passed to build_graph().
"""
import json
import os
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import boto3
from botocore.config import Config
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.graph import END, START, MessagesState, StateGraph

REGION = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION", "us-west-2")
CFG = Config(connect_timeout=5, read_timeout=60, retries={"max_attempts": 2, "mode": "standard"})
bedrock = boto3.client("bedrock-runtime", region_name=REGION, config=CFG)


class Tool:
    def __init__(self, name, description, properties, required, fn):
        self.name, self.description, self.fn = name, description, fn
        self.spec = {"toolSpec": {"name": name, "description": description, "inputSchema": {"json": {
            "type": "object", "properties": properties, "required": required}}}}


# ----------------------------------------------------------------- LangChain messages <-> Converse
def to_converse(messages):
    out = []

    def push(role, blocks):
        if not blocks:
            return
        if out and out[-1]["role"] == role:
            out[-1]["content"].extend(blocks)
        else:
            out.append({"role": role, "content": blocks})

    for m in messages:
        if isinstance(m, HumanMessage):
            push("user", [{"text": str(m.content)}])
        elif isinstance(m, AIMessage):
            blocks = [{"text": m.content}] if isinstance(m.content, str) and m.content.strip() else []
            blocks += [{"toolUse": {"toolUseId": tc["id"], "name": tc["name"], "input": tc["args"]}} for tc in m.tool_calls]
            push("assistant", blocks)
        elif isinstance(m, ToolMessage):
            push("user", [{"toolResult": {"toolUseId": m.tool_call_id, "status": "error" if m.status == "error" else "success",
                                          "content": [{"text": str(m.content)}]}}])
    # A pruned history may start mid-exchange: Converse needs a leading user text turn and
    # every toolResult must answer a toolUse in the previous assistant turn.
    while out and (out[0]["role"] != "user" or any("toolResult" in b for b in out[0]["content"])):
        out.pop(0)
    return out


def build_graph(tools, checkpointer, system_prompt):
    by_name = {t.name: t for t in tools}

    def model(state, config):
        kwargs = {"modelId": os.environ["MODEL_ID"], "messages": to_converse(state["messages"]),
                  "system": [{"text": system_prompt}],
                  "inferenceConfig": {"maxTokens": 800, "temperature": 0.2}}
        if tools:
            kwargs["toolConfig"] = {"tools": [t.spec for t in tools]}
        msg = bedrock.converse(**kwargs)["output"]["message"]
        text = "".join(b.get("text", "") for b in msg["content"])
        calls = [{"id": b["toolUse"]["toolUseId"], "name": b["toolUse"]["name"], "args": b["toolUse"]["input"]}
                 for b in msg["content"] if "toolUse" in b]
        return {"messages": [AIMessage(content=text, tool_calls=calls)]}

    def run_tools(state, config):
        ctx = config.get("configurable", {}).get("ctx", {})
        results = []
        for tc in state["messages"][-1].tool_calls:
            try:
                res, status = by_name[tc["name"]].fn(tc["args"], ctx), "success"
            except Exception as e:  # tool errors go back to the model, they don't crash the turn
                res, status = f"{type(e).__name__}: {e}", "error"
            results.append(ToolMessage(content=res if isinstance(res, str) else json.dumps(res, default=str),
                                       tool_call_id=tc["id"], status=status))
        return {"messages": results}

    def route(state):
        return "tools" if state["messages"][-1].tool_calls else END

    g = StateGraph(MessagesState)
    g.add_node("model", model)
    g.add_node("tools", run_tools)
    g.add_edge(START, "model")
    g.add_conditional_edges("model", route, ["tools", END])
    g.add_edge("tools", "model")
    return g.compile(checkpointer=checkpointer)


def run_turn(graph, prompt, config):
    """Run one user turn; return the answer plus what happened in this turn."""
    config = {"recursion_limit": 12, **config}
    before = len(graph.get_state(config).values.get("messages", [])) if graph.checkpointer else 0
    result = graph.invoke({"messages": [HumanMessage(content=prompt)]}, config)
    msgs = result["messages"]
    new = msgs[before:] if before <= len(msgs) else msgs
    used = [{"tool": tc["name"], "input": tc["args"]} for m in new if isinstance(m, AIMessage) for tc in m.tool_calls]
    errors = [m.content[:300] for m in new if isinstance(m, ToolMessage) and m.status == "error"]
    return {"answer": msgs[-1].content if isinstance(msgs[-1], AIMessage) else "",
            "tools_used": used,
            "trace": [{"thread_id": config["configurable"].get("thread_id"),
                       "messages_in_state": len(msgs)}] + [{"tool_error": e} for e in errors]}


# ----------------------------------------------------------------- AgentCore Runtime HTTP contract
def serve(handler, port=8080):
    class H(BaseHTTPRequestHandler):
        def _send(self, code, obj):
            body = json.dumps(obj, default=str).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            self._send(200, {"status": "Healthy"}) if self.path.startswith("/ping") else self._send(404, {})

        def do_POST(self):
            if not self.path.startswith("/invocations"):
                return self._send(404, {})
            try:
                payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            except json.JSONDecodeError:
                return self._send(400, {"error": "body must be JSON"})
            sid = self.headers.get("X-Amzn-Bedrock-AgentCore-Runtime-Session-Id", "local-session")
            try:
                result = handler(payload, sid)
            except Exception as e:
                print(traceback.format_exc(), flush=True)
                result = {"error": f"{type(e).__name__}: {e}"}
            print(json.dumps({"session": sid, "payload": payload, "result": result}, default=str)[:4000], flush=True)
            self._send(200, result)

        def log_message(self, *a):
            pass

    print(f"Trail Desk (LangGraph) listening on :{port}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", port), H).serve_forever()


# ----------------------------------------------------------------- reusable tool sources
def gateway_tools(gateway_url, inject=None):
    """Tools published by an AgentCore Gateway (MCP, AWS_IAM authorizer, SigV4-signed).

    inject: optional callable(args, ctx) -> args, applied by the APPLICATION before every call,
    e.g. to set the authenticated customer id. The model never sees or controls injected values.
    """
    import urllib.request
    from botocore.auth import SigV4Auth
    from botocore.awsrequest import AWSRequest
    session = boto3.Session(region_name=REGION)

    def mcp(method, params=None):
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}).encode()
        req = AWSRequest(method="POST", url=gateway_url, data=body,
                         headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"})
        SigV4Auth(session.get_credentials().get_frozen_credentials(), "bedrock-agentcore", REGION).add_auth(req)
        r = urllib.request.Request(gateway_url, data=body, method="POST", headers=dict(req.headers.items()))
        with urllib.request.urlopen(r, timeout=30) as resp:
            text = resp.read().decode()
        msg = json.loads(text) if text.lstrip().startswith("{") else \
            json.loads([l[5:] for l in text.splitlines() if l.startswith("data:")][-1])
        if "error" in msg:
            raise RuntimeError(f"MCP {method}: {msg['error']}")
        return msg["result"]

    tools = []
    for t in mcp("tools/list").get("tools", []):
        def call(args, ctx, name=t["name"]):
            if inject:
                args = inject(dict(args), ctx)
            res = mcp("tools/call", {"name": name, "arguments": args})
            text = "\n".join(c.get("text", "") for c in res.get("content", []))
            if res.get("isError"):
                raise RuntimeError(text)
            return text
        schema = t.get("inputSchema") or {"type": "object", "properties": {}}
        tools.append(Tool(t["name"], t.get("description") or t["name"], schema.get("properties", {}),
                          schema.get("required", []), call))
    return tools


def knowledge_base_tool(kb_id, name, description):
    """A Retrieve-based search tool over a Bedrock Knowledge Base."""
    kb = boto3.client("bedrock-agent-runtime", region_name=REGION, config=CFG)

    def search(args, ctx):
        out = kb.retrieve(knowledgeBaseId=kb_id, retrievalQuery={"text": args["query"]},
                          retrievalConfiguration={"vectorSearchConfiguration": {"numberOfResults": 4}})
        hits = [{"text": r["content"]["text"], "source": r.get("location", {}).get("s3Location", {}).get("uri")}
                for r in out["retrievalResults"]]
        return json.dumps(hits) if hits else "No matching passages found."

    return Tool(name, description, {"query": {"type": "string", "description": "what to look up"}}, ["query"], search)
