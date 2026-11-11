"""Scenario step for task 6: the export job delivers July 2024 web orders."""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "common"))
from awslab import outputs, put  # noqa: E402
from landing_data import datetime, jsonl, orders, timezone, web_orders_by_month  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--stack", default="cq-da-04")
b = outputs(ap.parse_args().stack)["LandingBucket"]
july = orders(n=850, days=31, start=datetime(2024, 7, 1, tzinfo=timezone.utc), id_offset=100000, seed_offset=9)
for (y, m), part in web_orders_by_month(july).items():
    put(b, f"web_orders/year={y}/month={m}/part-0000.json", jsonl(part), "application/json")
    put(b, f"web_orders/year={y}/month={m}/_SUCCESS", "")
