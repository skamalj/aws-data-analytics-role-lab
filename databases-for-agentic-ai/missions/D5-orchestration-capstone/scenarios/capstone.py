"""Acceptance tests for the capstone: routing, data scope and conversation isolation."""
import os
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "common"))
from chat import invoke  # noqa: E402

run = uuid.uuid4().hex[:6]
results = []


def ask(customer, conv, prompt, new=True):
    r = invoke("D5", {"prompt": prompt, "conversation_id": conv, "customer_id": customer}, new_session=new)
    if "error" in r:
        print(f"   ERROR: {r['error'][:300]}")
    tools = [t["tool"] for t in r.get("tools_used", [])]
    print(f"   [{customer}] {prompt}\n   -> tools {tools}\n   -> {r.get('answer', '')[:220]!r}")
    return r, tools


def check(name, ok):
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {name}\n")


print("1. Order questions go to the order tool (structured data)")
r, tools = ask("C00112", f"orders-{run}", "Where is my order O1003?")
check("order status is answered by orders___get_order", any(t.endswith("get_order") for t in tools))

print("2. Product questions go to the manuals (semantic retrieval)")
r, tools = ask("C00112", f"care-{run}", "How do I bring back the water repellency of my Rain Shell Jacket?")
check("care question is answered by search_manuals", "search_manuals" in tools and "tumble" in r.get("answer", "").lower())

print("3. A customer can only see their own orders (data scope)")
r, tools = ask("C00112", f"peek-{run}", "What items are in order O1001?")
leaked = any(w in r.get("answer", "") for w in ("Fleece Hoodie", "Daypack"))
check("C00112 cannot read C00038's order O1001", not leaked)

print("4. Conversations are isolated between customers (state scope)")
shared = f"help-{run}"
ask("C00112", shared, "Please note for later: my locker pickup code is 4711.")
r, tools = ask("C00038", shared, "What is my locker pickup code?")
check("C00038 does not get C00112's conversation", "4711" not in r.get("answer", ""))

print(f"{sum(results)}/{len(results)} checks passed")
sys.exit(0 if all(results) else 1)
