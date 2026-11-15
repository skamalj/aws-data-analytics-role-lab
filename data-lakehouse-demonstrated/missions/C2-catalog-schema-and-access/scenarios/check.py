"""C2 check: the feed lands without silent data loss, and category queries read only their partition."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "common"))
from lh import Athena, check, finish, safe  # noqa: E402

a = Athena()
cols = {r["column_name"]: r["data_type"] for r in a.rows(
    "SELECT column_name, data_type FROM information_schema.columns WHERE table_schema = 'riverbend_lakehouse' AND table_name = 'products'")}
check("products has the supplier's new column 'brand'", "brand" in cols, f"columns: {cols}")
check("price is stored as double (no float rounding)", cols.get("price") == "double", f"price: {cols.get('price')}")
r, err = safe(a.rows, "SELECT count(*) AS n, count(brand) AS b FROM riverbend_lakehouse.products")
st = r[0] if r else {}
check("all 61,000 SKUs present and the 2,000 feed rows carry a brand", st.get("n") == "61000" and st.get("b") == "2000", err or f"{st}")
r, err = safe(a.rows, "SELECT CAST(price AS varchar) AS p FROM riverbend_lakehouse.products WHERE product_id = 'SKU000001'")
check("feed price 20.95 is stored exactly", r and r[0]["p"] in ("20.95", "20.95E0", "2.095E1"), err or f"{r}")
q = "SELECT avg(price) FROM riverbend_lakehouse.products"
full, e1 = safe(a.stats, q)
part, e2 = safe(a.stats, q + " WHERE category = 'Tents'")
ratio = part["scanned"] / full["scanned"] if full and part and full["scanned"] else 1
check("a single-category query reads < 30% of what a full scan reads (partition pruning)", ratio < 0.30,
      e1 or e2 or f"{ratio:.0%} ({part['scanned']:,} of {full['scanned']:,} bytes)")
finish()
