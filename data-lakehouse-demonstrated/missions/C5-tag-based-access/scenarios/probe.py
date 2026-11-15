"""Run the same queries as each persona and show what they can see (no PASS/FAIL - use check.py for that)."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "common"))
from governed import as_persona, probe  # noqa: E402
from lh import mission  # noqa: E402

o = mission(os.path.join(HERE, ".."))
DB = o["database"]
for persona, arn in [("data-scientist", o["data_scientist_role_arn"]), ("intern", o["intern_role_arn"])]:
    a = as_persona(arn)
    for t in ["web_sessions", "product_reviews", "customers", "payroll"]:
        probe(persona, a, f"SELECT * FROM {DB}.{t} LIMIT 3")
    print()
