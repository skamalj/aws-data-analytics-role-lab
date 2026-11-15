"""
review_insights tool for Trail Desk's customer-intelligence questions ("how do customers feel about P101?").
Sentiment comes from Amazon Comprehend, called from SQL through Aurora machine learning (aws_ml).
"""
import json
import os
import time

import boto3

rds = boto3.client("rds-data")
DB = {"resourceArn": os.environ["CLUSTER_ARN"], "secretArn": os.environ["DB_SECRET_ARN"], "database": os.environ["DB_NAME"]}


def handler(event, context):
    product = str(event.get("product_id", ""))
    t0 = time.perf_counter()
    r = rds.execute_statement(
        sql="SELECT s.sentiment, count(*) AS reviews "
            "FROM commerce.reviews r, aws_comprehend.detect_sentiment(r.review_text, 'en') s "
            "WHERE r.product_id = :p GROUP BY s.sentiment ORDER BY reviews DESC",
        parameters=[{"name": "p", "value": {"stringValue": product}}], formatRecordsAs="JSON", **DB)
    return {"product_id": product, "sentiment": json.loads(r.get("formattedRecords") or "[]"),
            "db_ms": round((time.perf_counter() - t0) * 1000, 1)}
