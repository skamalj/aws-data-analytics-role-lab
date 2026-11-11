"""
Trail Desk capstone (mission D5): one LangGraph agent that routes between
  * structured data  - order lookups through the AgentCore Gateway (SQL on Aurora, app identity)
  * semantic search  - product manuals in a Bedrock Knowledge Base on Aurora pgvector
  * persistent state - conversation checkpoints in DynamoDB (langgraph-dynamodb-checkpoint)

Request: {"prompt": "...", "conversation_id": "...", "customer_id": "<from the web app's login session>"}
"""
import os

from agentstate_reducer import MessageReducer, ReducerConfig
from langgraph_dynamodb_checkpoint import DynamoDBSaver
from riverbend_graph import build_graph, gateway_tools, knowledge_base_tool, run_turn, serve

SYSTEM = ("You are Trail Desk, Riverbend Outfitters' customer assistant. Use your tools to answer; "
          "never invent order details or policies. Be concise and friendly.")

_graph = None


def graph():
    global _graph
    if _graph is None:
        tools = gateway_tools(os.environ["GATEWAY_URL"])
        tools.append(knowledge_base_tool(
            os.environ["KB_ID"], "search_manuals",
            "Riverbend's knowledge search. Use it to answer customer questions about orders, deliveries, "
            "shipping status, returns, warranties, products and how to use or care for gear."))
        saver = DynamoDBSaver(os.environ["CHECKPOINT_TABLE"], ttl_seconds=604800,
                              reducer=MessageReducer(config=ReducerConfig(max_messages=20, min_messages=10)))
        _graph = build_graph(tools, saver, SYSTEM)
    return _graph


def handle(payload, session_id):
    if not payload.get("prompt") or not payload.get("conversation_id"):
        return {"error": "payload needs 'prompt' and 'conversation_id'"}
    ctx = {"customer_id": payload.get("customer_id")}
    config = {"configurable": {"thread_id": f"support-{payload['conversation_id']}", "ctx": ctx}}
    return run_turn(graph(), payload["prompt"], config)


if __name__ == "__main__":
    serve(handle)
