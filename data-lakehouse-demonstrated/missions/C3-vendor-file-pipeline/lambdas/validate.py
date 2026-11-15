"""Validate a vendor CSV before loading: required columns present, at least one data row, quantities numeric."""
import csv
import io
import os
import urllib.parse

import boto3

s3 = boto3.client("s3")
REQUIRED = ["shipment_id", "vendor_id", "product_id", "quantity", "shipped_at"]


def handler(event, context):
    bucket, key = event["bucket"], urllib.parse.unquote_plus(event["key"])
    body = s3.get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8")
    reader = csv.DictReader(io.StringIO(body))
    missing = [c for c in REQUIRED if c not in (reader.fieldnames or [])]
    rows = list(reader)
    errors = [f"missing column {c}" for c in missing]
    if not rows:
        errors.append("no data rows")
    if not missing:
        bad = [r["shipment_id"] for r in rows if not str(r["quantity"]).isdigit()]
        if bad:
            errors.append(f"{len(bad)} rows with non-numeric quantity")
    return {"valid": not errors, "rows": len(rows), "errors": errors, "filename": os.path.basename(key)}
