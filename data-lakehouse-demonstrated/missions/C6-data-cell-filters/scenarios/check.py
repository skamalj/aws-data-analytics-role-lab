"""C6 check: data cell filters give marketing and the EU regional manager the right rows and columns."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "common"))
from datagen import governed_c6  # noqa: E402
from governed import as_persona, probe  # noqa: E402
from lh import check, finish, mission  # noqa: E402

o = mission(os.path.join(HERE, ".."))
T = f"{o['database']}.customer_profiles"
_, data = governed_c6()
opted = [r for r in data if r["marketing_opt_in"] == "true"]
eu = [r for r in data if r["region"] == "EU"]

mk = as_persona(o["marketing_role_arn"])
r, err = probe("marketing", mk, f"SELECT * FROM {T} LIMIT 5")
cols = set(r[0]) if r else set()
check("marketing can query customer_profiles", bool(r), err or "")
check("marketing sees no financial columns (credit_score, lifetime_value)", bool(r) and not cols & {"credit_score", "lifetime_value"}, f"columns: {sorted(cols)}")
check("marketing still sees email and segment", {"email", "segment"} <= cols, f"columns: {sorted(cols)}")
r, err = probe("marketing", mk, f"SELECT count(*) AS n FROM {T}")
n = int(r[0]["n"]) if r else None
check(f"marketing sees exactly the {len(opted)} opted-in customers", n == len(opted), err or f"got {n}")

eum = as_persona(o["eu_manager_role_arn"])
r, err = probe("eu-manager", eum, f"SELECT region, count(*) AS n, round(sum(lifetime_value), 2) AS ltv FROM {T} GROUP BY region")
regions = {x["region"]: x for x in r or []}
check("EU manager can query customer_profiles", r is not None, err or "")
check("EU manager sees only EU rows", set(regions) == {"EU"}, f"regions: {sorted(regions)}")
want = round(sum(x["lifetime_value"] for x in eu), 2)
got = regions.get("EU", {})
check(f"EU manager sees all {len(eu)} EU customers (lifetime value {want:,.2f})",
      got.get("n") == str(len(eu)) and abs(float(got.get("ltv") or 0) - want) < 0.01, f"{got}")
r, err = probe("eu-manager", eum, f"SELECT * FROM {T} LIMIT 5")
cols = set(r[0]) if r else set()
check("EU manager does not see credit_score but does see lifetime_value", bool(r) and "credit_score" not in cols and "lifetime_value" in cols,
      err or f"columns: {sorted(cols)}")
finish()
