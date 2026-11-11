"""Seed a full year of orders (200,000 rows), one CSV file per month."""
import argparse
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "common"))
from awslab import outputs, put  # noqa: E402
from datagen import customers, orders, products, to_csv, to_jsonl  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--stack", required=True)
bkt = outputs(ap.parse_args().stack)["RawBucket"]

by_month = defaultdict(list)
for o in orders(n=200_000, days=366):
    by_month[o["order_ts"][:7]].append(o)
for month, rows in sorted(by_month.items()):
    put(bkt, f"orders/orders_{month}.csv", to_csv(rows), "text/csv")
put(bkt, "customers/customers.csv", to_csv(customers()), "text/csv")
put(bkt, "products/products.json", to_jsonl(products()), "application/json")
