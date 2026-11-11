"""Upload a year of sales and create the reporting view riverbend_bi.v_sales."""
import argparse
import os
import sys

import boto3

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "common"))
from athena_run import run  # noqa: E402
from awslab import outputs, put  # noqa: E402
from datagen import customers, orders, products, to_csv  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--stack", required=True)
stack = ap.parse_args().stack
out = outputs(stack)
b = out["LakeBucket"]
put(b, "orders/orders_2024.csv", to_csv(orders(n=200_000, days=366)), "text/csv")
put(b, "customers/customers.csv", to_csv(customers()), "text/csv")
put(b, "products/products.csv", to_csv(products()), "text/csv")

VIEW = """
CREATE OR REPLACE VIEW riverbend_bi.v_sales AS
SELECT o.order_id, o.order_ts, CAST(o.order_ts AS date) AS order_date,
       o.channel, o.store_id, o.region, o.status, o.quantity, o.discount, o.total_amount,
       p.product_name, p.category,
       c.customer_id, c.country, c.city, c.loyalty_tier
FROM riverbend_bi.orders o
JOIN riverbend_bi.products  p ON p.product_id  = o.product_id
JOIN riverbend_bi.customers c ON c.customer_id = o.customer_id
"""
if not run(boto3.client("athena"), VIEW.strip(), out["AthenaWorkGroup"]):
    sys.exit("could not create view")
