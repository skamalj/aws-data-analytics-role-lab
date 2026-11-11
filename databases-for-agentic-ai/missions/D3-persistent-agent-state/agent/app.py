"""
Trail Desk returns assistant (mission D3): a LangGraph agent whose conversation state is
checkpointed in Amazon DynamoDB with langgraph-dynamodb-checkpoint, so a customer can leave
and come back later - in a new runtime session - and continue where they stopped.

Request: {"prompt": "...", "conversation_id": "<stable id from the web app>", "customer_id": "C00042"}
"""
import os
from datetime import date

from langgraph_dynamodb_checkpoint import DynamoDBSaver
from riverbend_graph import Tool, build_graph, run_turn, serve

SYSTEM = ("You are Trail Desk, Riverbend Outfitters' returns assistant. Help customers return items: "
          "look the order up, check eligibility, ask for the reason if you don't have it, then create the return. "
          "Use the tools; never invent order details. Be concise.")

ORDERS = {
    "O2001": {"status": "DELIVERED", "delivered": "2026-11-02", "items": ["Ultralight Stove"], "used": True},
    "O2002": {"status": "SHIPPED", "delivered": None, "items": ["Ridge Hiking Boot"], "used": False},
    "O2003": {"status": "DELIVERED", "delivered": "2026-10-28", "items": ["Trailhead 2P Tent"], "used": False},
}
RETURNS = {}


def lookup_order(args, ctx):
    o = ORDERS.get(str(args.get("order_id", "")).upper())
    return {"order_id": args["order_id"].upper(), **o} if o else {"error": "order not found"}


def check_return_eligibility(args, ctx):
    oid = str(args.get("order_id", "")).upper()
    o = ORDERS.get(oid)
    if not o:
        return {"eligible": False, "why": "order not found"}
    if o["status"] != "DELIVERED":
        return {"eligible": False, "why": f"order is {o['status']}; only delivered orders can be returned"}
    if "Ultralight Stove" in o["items"] and o["used"]:
        return {"eligible": False, "why": "used stoves can only be returned if defective"}
    days = (date(2026, 11, 11) - date.fromisoformat(o["delivered"])).days
    return {"eligible": days <= 60, "days_since_delivery": days, "next_step": "ask the customer for the reason"}


def create_return(args, ctx):
    oid = str(args.get("order_id", "")).upper()
    if not check_return_eligibility({"order_id": oid}, ctx).get("eligible"):
        return {"error": "order is not eligible for return"}
    rma = f"RMA-{oid[1:]}-{len(RETURNS) + 1:02d}"
    RETURNS[rma] = {"order_id": oid, "reason": args.get("reason")}
    return {"return_id": rma, "label_url": f"https://returns.example.com/{rma}.pdf"}


def fit_guide(args, ctx):
    """The full fit & sizing guide (it is long - about 30 KB)."""
    product = args.get("product", "product")
    rows = [f"| EU {s} | UK {s - 33} | US {s - 32} | foot length {22.5 + (s - 36) * 0.65:.1f} cm | "
            f"width {w} | note: {product} runs true to size; for thick socks or wide feet go half a size up |"
            for s in range(36, 49) for w in ("narrow", "regular", "wide", "extra wide")]
    return f"FIT GUIDE - {product}\n" + "\n".join(rows * 4)


TOOLS = [
    Tool("lookup_order", "Look up a customer's order: status, delivery date and items.",
         {"order_id": {"type": "string", "description": "order id, e.g. O2003"}}, ["order_id"], lookup_order),
    Tool("check_return_eligibility", "Check whether an order can be returned, before creating a return.",
         {"order_id": {"type": "string"}}, ["order_id"], check_return_eligibility),
    Tool("create_return", "Create a return for an eligible order once you know the reason. Returns an RMA id and label.",
         {"order_id": {"type": "string"}, "reason": {"type": "string", "description": "the customer's reason"}},
         ["order_id", "reason"], create_return),
    Tool("fit_guide", "Get the complete fit and sizing guide for a product (all sizes and widths).",
         {"product": {"type": "string"}}, ["product"], fit_guide),
]

_graph = None


def graph():
    global _graph
    if _graph is None:   # built on first request so configuration errors are returned, not crash the runtime
        saver = DynamoDBSaver(os.environ["CHECKPOINT_TABLE"])
        _graph = build_graph(TOOLS, saver, SYSTEM)
    return _graph


def handle(payload, session_id):
    if not payload.get("prompt"):
        return {"error": "payload needs a 'prompt'"}
    config = {"configurable": {"thread_id": session_id,
                               "ctx": {"customer_id": payload.get("customer_id")}}}
    return run_turn(graph(), payload["prompt"], config)


if __name__ == "__main__":
    serve(handle)
