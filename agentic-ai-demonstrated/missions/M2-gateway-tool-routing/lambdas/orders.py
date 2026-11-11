"""Riverbend order service, exposed to agents as MCP tools through AgentCore Gateway."""
import json

ORDERS = {
    "O1001": {"status": "SHIPPED", "carrier": "TrailPost", "tracking": "TP-88231", "eta": "2026-11-14",
              "items": ["Trailhead 2P Tent"]},
    "O1002": {"status": "PROCESSING", "carrier": None, "tracking": None, "eta": "2026-11-18",
              "items": ["Ridge Hiking Boot", "Merino Base Layer"]},
    "O1003": {"status": "DELIVERED", "carrier": "TrailPost", "tracking": "TP-87002", "eta": "2026-11-02",
              "items": ["Ultralight Stove"]},
}
RETURNS = {}


def get_order_status(args):
    order = ORDERS.get(str(args.get("order_id", "")).upper())
    return order and {"order_id": args["order_id"].upper(), **order} or {"error": "order not found"}


def start_return(args):
    oid = str(args.get("order_id", "")).upper()
    if oid not in ORDERS:
        return {"error": "order not found"}
    if ORDERS[oid]["status"] != "DELIVERED":
        return {"error": f"order {oid} is {ORDERS[oid]['status']}; only delivered orders can be returned"}
    rma = f"RMA-{oid[1:]}-{len(RETURNS) + 1:02d}"
    RETURNS[rma] = {"order_id": oid, "reason": args.get("reason", "unspecified")}
    return {"return_id": rma, "label_url": f"https://returns.example.com/{rma}.pdf"}


HANDLERS = {"get_order_status": get_order_status, "start_return": start_return}


def handler(event, context):
    # AgentCore Gateway passes the tool arguments as the event and the tool name in the client context.
    tool = context.client_context.custom["bedrockAgentCoreToolName"]
    print(json.dumps({"tool": tool, "arguments": event}))
    fn = HANDLERS.get(tool)
    if not fn:
        return {"error": f"unknown tool '{tool}'"}
    return fn(event)
