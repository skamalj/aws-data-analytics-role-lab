"""Load CRM profiles into DynamoDB and orders into S3."""
import argparse
import os
import sys

import boto3

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "common"))
from awslab import outputs, put  # noqa: E402
from datagen import customer_profiles, orders, to_csv  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--stack", required=True)
out = outputs(ap.parse_args().stack)

put(out["LakeBucket"], "orders/orders_2024_h1.csv", to_csv(orders()), "text/csv")

table = boto3.resource("dynamodb").Table(out["DynamoDBTable"])
with table.batch_writer(overwrite_by_pkeys=["customer_id"]) as bw:
    for item in customer_profiles():
        bw.put_item(Item=item)
print(f"  wrote {len(customer_profiles())} items to DynamoDB table {out['DynamoDBTable']}")
