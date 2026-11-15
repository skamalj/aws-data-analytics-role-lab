"""Show what marketing and the EU regional manager see in customer_profiles (no PASS/FAIL - use check.py)."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "common"))
from governed import as_persona, probe  # noqa: E402
from lh import mission  # noqa: E402

o = mission(os.path.join(HERE, ".."))
T = f"{o['database']}.customer_profiles"
for persona, arn in [("marketing", o["marketing_role_arn"]), ("eu-manager", o["eu_manager_role_arn"])]:
    a = as_persona(arn)
    probe(persona, a, f"SELECT * FROM {T} LIMIT 3")
    rows, _ = probe(persona, a, f"SELECT region, marketing_opt_in, count(*) AS n FROM {T} GROUP BY 1, 2 ORDER BY 1, 2")
    for r in rows or []:
        print("      ", r)
    print()
