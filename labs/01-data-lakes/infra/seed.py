"""Seed the raw bucket with the files the business 'exported' from its systems."""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "common"))
from awslab import outputs, put  # noqa: E402
from datagen import customers, orders, products, to_csv, to_jsonl  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--stack", required=True)
out = outputs(ap.parse_args().stack)
bkt = out["RawBucket"]

put(bkt, "sales/orders/orders_2024_h1.csv", to_csv(orders()), "text/csv")
put(bkt, "sales/customers/customers.csv", to_csv(customers()), "text/csv")
put(bkt, "sales/products/products.json", to_jsonl(products()), "application/json")
