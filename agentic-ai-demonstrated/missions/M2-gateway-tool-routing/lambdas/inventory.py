"""Riverbend inventory service, exposed to agents as an MCP tool through AgentCore Gateway."""
import json

STOCK = {
    "trailhead 2p tent": {"S01": 4, "S07": 0, "S12": 9},
    "ridge hiking boot": {"S01": 12, "S07": 3, "S12": 0},
    "ultralight stove": {"S01": 0, "S07": 6, "S12": 2},
}
DELIMITER = "___"   # gateway tool names are "<target name>___<tool name>"


def handler(event, context):
    full_name = context.client_context.custom["bedrockAgentCoreToolName"]
    tool = full_name.split(DELIMITER, 1)[-1]
    print(json.dumps({"tool": full_name, "arguments": event}))
    if tool != "check_stock":
        return {"error": f"unknown tool '{tool}'"}
    levels = STOCK.get(str(event.get("product", "")).lower())
    if not levels:
        return {"error": "unknown product", "known_products": sorted(STOCK)}
    store = event.get("store_id")
    return {"product": event["product"], "stock": {store: levels.get(store, 0)} if store else levels}
