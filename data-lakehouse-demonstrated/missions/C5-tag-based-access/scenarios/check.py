"""C5 check: LF-Tag grants give data science and interns exactly the access in the policy."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "common"))
from governed import as_persona, probe  # noqa: E402
from lh import check, finish, mission  # noqa: E402

o = mission(os.path.join(HERE, ".."))
DB = o["database"]
ds, intern = as_persona(o["data_scientist_role_arn"]), as_persona(o["intern_role_arn"])


def count(a, who, t):
    r, err = probe(who, a, f"SELECT count(*) AS n FROM {DB}.{t}")
    return int(r[0]["n"]) if r else None


EXPECT = {"web_sessions": 1000, "product_reviews": 300}
for t, n in EXPECT.items():
    got = count(ds, "data-scientist", t)
    check(f"data scientist can read {t} ({n} rows)", got == n, f"got {got}")
    got = count(intern, "intern", t)
    check(f"intern can read {t} ({n} rows)", got == n, f"got {got}")

r, err = probe("data-scientist", ds, f"SELECT * FROM {DB}.customers LIMIT 5")
cols = set(r[0]) if r else set()
check("data scientist can read customers", r is not None and len(r) == 5, err or "")
check("data scientist sees no PII columns in customers (email, phone)", r is not None and not cols & {"email", "phone"}, f"columns: {sorted(cols)}")
check("data scientist still sees the non-PII columns (customer_id, region, segment, lifetime_value)",
      {"customer_id", "region", "segment", "lifetime_value"} <= cols, f"columns: {sorted(cols)}")

r, _ = probe("data-scientist", ds, f"SELECT count(*) FROM {DB}.payroll")
check("data scientist cannot read payroll (HR)", r is None)
r, _ = probe("intern", intern, f"SELECT count(*) FROM {DB}.customers")
check("intern cannot read customers (confidential)", r is None)
r, _ = probe("intern", intern, f"SELECT count(*) FROM {DB}.payroll")
check("intern cannot read payroll", r is None)
finish()
