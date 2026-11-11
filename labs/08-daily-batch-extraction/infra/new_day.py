"""
Scenario driver: one business day happens in the order system.
Inserts the new orders for --date and marks some older orders RETURNED (an UPDATE),
both stamped with updated_at on that date.

    python3 labs/08-daily-batch-extraction/infra/new_day.py --date 2024-07-01
"""
import argparse
import os
import random
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sourcedb import SourceDb  # noqa: E402
from datagen import orders  # noqa: E402


def day_changes(date):
    d = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    seq = (d - datetime(2024, 7, 1, tzinfo=timezone.utc)).days
    new = orders(n=300, days=1, start=d, id_offset=300000 + seq * 1000, seed_offset=100 + seq)
    new = [dict(o, updated_at=o["order_ts"]) for o in new]
    r = random.Random(seq)
    returned = []
    for o in r.sample(orders(), 12):     # 12 earlier orders come back today
        if o["status"] == "COMPLETED":
            returned.append(dict(o, status="RETURNED", updated_at=f"{date} 18:{r.randint(10, 59)}:00"))
    return new, returned


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stack", default="cq-da-08")
    ap.add_argument("--date", required=True)
    a = ap.parse_args()
    db = SourceDb(a.stack)
    new, returned = day_changes(a.date)
    db.insert_orders(new)
    db.insert_orders(returned, upsert=True)
    print(f"  {a.date}: {len(new)} new orders, {len(returned)} orders updated to RETURNED")
