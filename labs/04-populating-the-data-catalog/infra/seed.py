"""Seed the landing zone for Lab 04 (January to June 2024)."""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "common"))
from awslab import outputs, put  # noqa: E402
from landing_data import (clickstream_day, datetime, gz, jsonl, orders, returns_rows,  # noqa: E402
                          store_sales_files, timezone, to_csv, web_orders_by_month)

ap = argparse.ArgumentParser()
ap.add_argument("--stack", required=True)
b = outputs(ap.parse_args().stack)["LandingBucket"]
rows = orders()

# 1. Hive-style partitioned JSON Lines, plus "_SUCCESS" markers written by the export job
for (y, m), part in sorted(web_orders_by_month(rows).items()):
    put(b, f"web_orders/year={y}/month={m}/part-0000.json", jsonl(part), "application/json")
    put(b, f"web_orders/year={y}/month={m}/_SUCCESS", "")
# ...and a half-uploaded temp file that someone's laptop left behind (it is CSV, not JSON!)
put(b, "web_orders/year=2024/month=03/upload_in_progress.tmp", to_csv(rows[:50]))

# 2. Pipe-delimited POS extracts with no header row
for month, body in sorted(store_sales_files(rows).items()):
    put(b, f"store_sales/pos_extract_{month}.psv", body)

# 3. Returns, CSV with header, one file plain, one gzip-compressed
ret = returns_rows(rows)
half = len(ret) // 2
put(b, "returns/returns_part1.csv", to_csv(ret[:half]), "text/csv")
put(b, "returns/returns_part2.csv.gz", gz(to_csv(ret[half:])), "application/gzip")

# 4. Clickstream in non-Hive folders: clickstream/YYYY/MM/DD/
for d in range(1, 8):
    day = datetime(2024, 6, d, tzinfo=timezone.utc)
    put(b, f"clickstream/{day:%Y/%m/%d}/events.json", jsonl(clickstream_day(day)), "application/json")
