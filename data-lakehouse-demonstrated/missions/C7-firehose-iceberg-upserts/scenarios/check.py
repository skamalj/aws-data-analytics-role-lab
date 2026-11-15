"""C7 check: the stream upserts into Iceberg - one row per order with its latest status, deletes applied, no delivery errors."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "common"))
from datagen import order_status_waves  # noqa: E402
from lh import Athena, base, check, finish, mission, safe, session  # noqa: E402

b, o = base(), mission(os.path.join(HERE, ".."))
_, want = order_status_waves()
a = Athena()

errs = session().client("s3").list_objects_v2(Bucket=b["lake_bucket"], Prefix=o["error_prefix"]).get("KeyCount", 0)
check("no records in the Firehose error prefix", errs == 0, f"{errs} error object(s) under s3://{b['lake_bucket']}/{o['error_prefix']}")

rows, err = safe(a.rows, "SELECT order_id, status, count(*) OVER (PARTITION BY order_id) AS c FROM riverbend_lakehouse.order_status")
rows = rows or []
check("records were delivered to riverbend_lakehouse.order_status", len(rows) > 0, err or f"{len(rows)} rows")
dupes = {r["order_id"] for r in rows if r["c"] != "1"}
check("exactly one row per order (updates are upserts, not appends)", rows and not dupes, f"{len(dupes)} orders with >1 row")
got = {r["order_id"]: r["status"] for r in rows}
check(f"{len(want)} orders present (200 inserted, 20 deleted)", len(got) == len(want), f"{len(got)} distinct orders")
gone = [k for k in got if k not in want]
check("the 20 purged test orders are deleted", not gone, f"still present: {len(gone)}")
wrong = [k for k, (st, _) in want.items() if got.get(k) not in (None, st)]
check("every order shows its latest status", got and not wrong and len(got) == len(want), f"{len(wrong)} with a stale status")
finish()
