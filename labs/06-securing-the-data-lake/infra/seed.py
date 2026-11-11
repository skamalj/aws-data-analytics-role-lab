"""Seed customers (with PII) and orders into the lake bucket."""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "common"))
from awslab import outputs, put  # noqa: E402
from datagen import customers, orders, to_csv  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--stack", required=True)
b = outputs(ap.parse_args().stack)["LakeBucket"]
put(b, "customers/customers.csv", to_csv(customers()), "text/csv")
put(b, "orders/orders_2024_h1.csv", to_csv(orders()), "text/csv")
