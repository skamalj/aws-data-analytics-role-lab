"""Create the operational schema and load January-June 2024 orders into Aurora."""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sourcedb import SourceDb  # noqa: E402
from datagen import orders  # noqa: E402  (path set up by sourcedb)

DDL = [
    "CREATE SCHEMA IF NOT EXISTS sales",
    """CREATE TABLE IF NOT EXISTS sales.orders (
         order_id     VARCHAR(10) PRIMARY KEY,
         order_ts     TIMESTAMP NOT NULL,
         customer_id  VARCHAR(10) NOT NULL,
         product_id   VARCHAR(10) NOT NULL,
         quantity     INT NOT NULL,
         unit_price   NUMERIC(10,2) NOT NULL,
         discount     NUMERIC(4,2) NOT NULL,
         total_amount NUMERIC(12,2) NOT NULL,
         channel      VARCHAR(10),
         store_id     VARCHAR(5),
         region       VARCHAR(10),
         status       VARCHAR(10) NOT NULL,
         updated_at   TIMESTAMP NOT NULL
       )""",
    "CREATE INDEX IF NOT EXISTS orders_updated_at_idx ON sales.orders (updated_at)",
    "TRUNCATE sales.orders",
]

ap = argparse.ArgumentParser()
ap.add_argument("--stack", required=True)
db = SourceDb(ap.parse_args().stack)
for s in DDL:
    db.sql(s)
rows = [dict(o, updated_at=o["order_ts"]) for o in orders()]
db.insert_orders(rows)
