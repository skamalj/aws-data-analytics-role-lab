"""
Write realistic Trail Desk conversation state into the D7 memory table, through
langgraph-dynamodb-checkpoint exactly as the agent does (no model calls; the replies are scripted).

    pip install -r missions/D7-dynamodb-mcp-state-inspection/scenarios/requirements.txt
    python3 missions/D7-dynamodb-mcp-state-inspection/scenarios/seed_conversations.py
"""
import os
import sys

os.environ.setdefault("AGENTSTATE_QUIET", "1")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "common"))
from checks import mission_outputs  # noqa: E402
from langchain_core.messages import AIMessage, HumanMessage  # noqa: E402
from langgraph.graph import START, MessagesState, StateGraph  # noqa: E402
from langgraph_dynamodb_checkpoint import DynamoDBSaver  # noqa: E402

out = mission_outputs(os.path.join(HERE, ".."))
os.environ.setdefault("AWS_REGION", out["region"])
os.environ.setdefault("AWS_DEFAULT_REGION", out["region"])
saver = DynamoDBSaver(out["memory_table"], ttl_seconds=7 * 86400)

REPLIES = iter([])


def scripted(state):
    return {"messages": [AIMessage(content=next(REPLIES))]}


g = StateGraph(MessagesState)
g.add_node("agent", scripted)
g.add_edge(START, "agent")
graph = g.compile(checkpointer=saver)

CONVERSATIONS = {
    "support-C00112-c1": [("Hi, I'm Dana. My order O1003 hasn't arrived. Reach me at dana.k@example.com or +1-555-0177.",
                           "Thanks Dana, O1003 shipped on 2026-02-09 via TrailPost; I'll email updates to dana.k@example.com.")],
    "support-C00038-c1": [("I want to return the Fleece Hoodie from O1001, it's too small.",
                           "No problem - O1001 is eligible. I created return RMA-1001-01; the label is in your inbox.")],
    "support-C00075-c7": [("Which rope do you recommend for indoor climbing?", "The Dynamic Rope 60m is our all-rounder."),
                          ("And a harness? My phone is +1-555-0199 if a store needs to call.",
                           "Pair it with the Harness (P116). Store S07 can call you on +1-555-0199.")],
    "returns-C00241-r2": [("Order O1020 was cancelled but I was charged.", "I've raised a refund check for O1020.")],
    "sizing-C00042-s1": [(f"Fit guide request {i}: boots, size EU {38 + i}", "FIT GUIDE " + "| EU size row | " * 300)
                         for i in range(25)],
}

for thread, turns in CONVERSATIONS.items():
    REPLIES = iter([a for _, a in turns])
    for q, _ in turns:
        graph.invoke({"messages": [HumanMessage(content=q)]}, {"configurable": {"thread_id": thread}})
    print(f"  seeded {thread} ({len(turns)} turns)")
print(f"done: {len(CONVERSATIONS)} threads in {out['memory_table']}")
