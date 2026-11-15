"""C1 check: one row per order, each with its latest status, and correct revenue."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "common"))
import datagen  # noqa: E402
from lh import Athena, check, finish, safe  # noqa: E402

exp = datagen.expected_orders()
a = Athena()
r, err = safe(a.rows, "SELECT count(*) AS n, count(DISTINCT order_id) AS d FROM riverbend_lakehouse.orders")
n = r[0] if r else {}
check("every order is ingested exactly once (600 rows, 600 distinct order_id)",
      n.get("n") == "600" and n.get("d") == "600", err or f"{n}")
r, err = safe(a.rows, "SELECT order_id, status, CAST(updated_at AS varchar) AS u FROM riverbend_lakehouse.orders")
wrong = [x["order_id"] for x in (r or []) if x["order_id"] in exp and x["status"] != exp[x["order_id"]]["status"]]
check("each order carries its latest status (replays and same-day changes handled)", r is not None and not wrong,
      err or (f"{len(wrong)} orders with a stale status, e.g. {wrong[:3]}" if wrong else ""))
r, err = safe(a.rows, "SELECT status, count(*) AS n FROM riverbend_lakehouse.orders GROUP BY status ORDER BY status")
by = {x["status"]: int(x["n"]) for x in (r or [])}
check("status totals match the source of truth (PLACED 480, SHIPPED 100, CANCELLED 20)",
      by == {"PLACED": 480, "SHIPPED": 100, "CANCELLED": 20}, err or f"{by}")
r, err = safe(a.rows, "SELECT round(sum(amount), 2) AS rev FROM riverbend_lakehouse.orders WHERE status <> 'CANCELLED'")
check("non-cancelled revenue is 110120.00", r and float(r[0]["rev"] or 0) == 110120.0, err or f"{r}")
finish()
