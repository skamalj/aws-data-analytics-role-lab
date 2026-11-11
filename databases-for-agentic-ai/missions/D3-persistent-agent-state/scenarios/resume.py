"""Scenario: a customer starts a return, leaves, and comes back later in a NEW runtime session."""
import os
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "common"))
from chat import invoke, show  # noqa: E402

conv = f"alex-{uuid.uuid4().hex[:6]}"
print(f"conversation_id = {conv}\n--- visit 1 (session A)")
r1 = invoke("D3", {"prompt": "Hi, I'd like to return my order O2003.", "conversation_id": conv,
                   "customer_id": "C00042"}, new_session=True)
show(r1)
print("\n--- visit 2, an hour later (session B)")
r2 = invoke("D3", {"prompt": "Sorry, I had to go. The reason is that it's too heavy for solo trips.",
                   "conversation_id": conv, "customer_id": "C00042"}, new_session=True)
show(r2)
ok = any(t["tool"] == "create_return" and str(t["input"].get("order_id", "")).upper() == "O2003"
         for t in r2.get("tools_used", []))
print("\nRESUME:", "PASS - the return for O2003 was created in the new session" if ok else
      "FAIL - the agent did not continue the O2003 return in the new session")
