"""Scenario: a long conversation with large tool results (fit guides are ~30 KB each)."""
import os
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "common"))
from chat import invoke  # noqa: E402

conv = f"sizing-{uuid.uuid4().hex[:6]}"
products = ["Ridge Hiking Boot", "Trail Runner", "Camp Sandal", "Rain Shell Jacket", "Merino Base Layer"]
print(f"conversation_id = {conv}")
for turn in range(1, 21):
    p = products[turn % len(products)]
    r = invoke("D3", {"prompt": f"Please show me the complete fit guide for the {p}, then summarise it in one line.",
                      "conversation_id": conv, "customer_id": "C00042"}, new_session=(turn == 1))
    if "error" in r:
        print(f"turn {turn:2d}: ERROR {r['error'][:200]}")
        print("LONG CHAT: FAIL")
        sys.exit(1)
    msgs = (r.get("trace") or [{}])[0].get("messages_in_state")
    print(f"turn {turn:2d}: ok  (messages in state: {msgs})")
print("LONG CHAT: PASS - 20 turns without errors")
