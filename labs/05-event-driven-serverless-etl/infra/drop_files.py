"""
Scenario driver: simulates the order system delivering daily CSV files to the
landing bucket.

    python3 labs/05-event-driven-serverless-etl/infra/drop_files.py          # days 1-3 of July 2024
    python3 labs/05-event-driven-serverless-etl/infra/drop_files.py --bad    # day 4, with corrupt rows
"""
import argparse
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "common"))
from awslab import outputs, put  # noqa: E402
from datagen import orders, to_csv  # noqa: E402

BAD_LINES = [
    "O0299991,2024-07-04 10:00:00,C00010,P101,abc,189.0,0,189.0,web,S01,NA,COMPLETED",   # quantity not a number
    "O0299992,2024-07-04 10:05:00,C00011,P102",                                           # truncated row
    "O0299993,2024-07-04 10:10:00,C00012,P103,-2,129.0,0,-258.0,store,S02,EU,COMPLETED",  # negative quantity
    ",2024-07-04 10:15:00,C00013,P104,1,159.0,0,159.0,web,S03,APAC,COMPLETED",            # missing order_id
    "O0299995,not-a-date,C00014,P105,1,119.0,0,119.0,mobile,S04,LATAM,COMPLETED",          # bad timestamp
]


def daily_files():
    rows = orders(n=1200, days=4, start=datetime(2024, 7, 1, tzinfo=timezone.utc),
                  id_offset=200000, seed_offset=11)
    by_day = defaultdict(list)
    for r in rows:
        by_day[r["order_ts"][:10]].append(r)
    return by_day


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stack", default="cq-da-05")
    ap.add_argument("--bad", action="store_true", help="deliver the day-4 file containing corrupt rows")
    a = ap.parse_args()
    bucket = outputs(a.stack)["LandingBucket"]
    days = daily_files()
    keys = sorted(days)
    if a.bad:
        body = to_csv(days[keys[3]]) + "\n".join(BAD_LINES) + "\n"
        put(bucket, f"incoming/orders/orders_{keys[3]}.csv", body, "text/csv")
        return
    for i, day in enumerate(keys[:3]):
        rows = days[day]
        if i == 1:  # the POS gateway retried and sent 15 lines twice
            rows = rows + rows[:15]
        put(bucket, f"incoming/orders/orders_{day}.csv", to_csv(rows), "text/csv")


if __name__ == "__main__":
    main()
