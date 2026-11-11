"""Print what the pipeline has produced so far (counts, recent alerts, dead-lettered records)."""
import argparse
import base64
import json
import os
import sys
import urllib.request

import boto3

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "common"))
from awslab import outputs  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--stack", default="cq-da-10")
out = outputs(ap.parse_args().stack)
sec = json.loads(boto3.client("secretsmanager").get_secret_value(SecretId=out["OpenSearchSecretArn"])["SecretString"])
auth = base64.b64encode(f"{sec['username']}:{sec['password']}".encode()).decode()


def q(path, body=None):
    req = urllib.request.Request(f"https://{out['OpenSearchEndpoint']}{path}",
                                 data=json.dumps(body).encode() if body else None,
                                 headers={"Content-Type": "application/json", "Authorization": f"Basic {auth}"},
                                 method="POST" if body else "GET")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


for idx in ["freezer-readings-*", "freezer-window-stats", "freezer-alerts"]:
    try:
        print(f"{idx:22} {q(f'/{idx}/_count')['count']:>8} docs")
    except Exception as e:  # index may not exist yet
        print(f"{idx:22} not yet ({e})")
try:
    hits = q("/freezer-alerts/_search", {"size": 10, "sort": [{"window_start": "desc"}]})["hits"]["hits"]
    print("\nlatest alerts:")
    for h in hits:
        print("  ", h["_source"]["message"])
except Exception:
    pass
attrs = boto3.client("sqs").get_queue_attributes(QueueUrl=out["FailedRecordsQueueUrl"],
                                                  AttributeNames=["ApproximateNumberOfMessages"])
print(f"\nSQS failed-records queue: {attrs['Attributes']['ApproximateNumberOfMessages']} messages")
