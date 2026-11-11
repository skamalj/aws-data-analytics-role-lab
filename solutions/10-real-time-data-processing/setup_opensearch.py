"""
Configure the lab OpenSearch domain as the master user (credentials from Secrets Manager):
  1. role 'freezer_writer' that may write freezer-* indices, mapped to the processor Lambda's IAM role
  2. index template for freezer-* (dates, keywords, floats)
  3. Dashboards index patterns for readings, window stats and alerts

    python3 setup_opensearch.py --stack cq-da-10
"""
import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request

import boto3

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "common"))
from awslab import outputs  # noqa: E402


def call(host, auth, method, path, body=None, dashboards=False):
    headers = {"Content-Type": "application/json", "Authorization": f"Basic {auth}"}
    if dashboards:
        headers["osd-xsrf"] = "true"
    req = urllib.request.Request(f"https://{host}{path}", method=method, headers=headers,
                                 data=json.dumps(body).encode() if body is not None else None)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            print(f"  {method} {path} -> {r.status}")
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        print(f"  {method} {path} -> {e.code} {e.read()[:300]}")
        if e.code != 409:   # 409 = already exists
            raise


ap = argparse.ArgumentParser()
ap.add_argument("--stack", default="cq-da-10")
out = outputs(ap.parse_args().stack)
host = out["OpenSearchEndpoint"]
sec = json.loads(boto3.client("secretsmanager").get_secret_value(SecretId=out["OpenSearchSecretArn"])["SecretString"])
auth = base64.b64encode(f"{sec['username']}:{sec['password']}".encode()).decode()

call(host, auth, "PUT", "/_plugins/_security/api/roles/freezer_writer", {
    "cluster_permissions": ["cluster_composite_ops", "indices:data/write/bulk*"],
    "index_permissions": [{"index_patterns": ["freezer-*"],
                           "allowed_actions": ["crud", "create_index", "indices:admin/mapping/put"]}]})
call(host, auth, "PUT", "/_plugins/_security/api/rolesmapping/freezer_writer",
     {"backend_roles": [out["ProcessorRoleArn"]]})

call(host, auth, "PUT", "/_index_template/freezer", {
    "index_patterns": ["freezer-*"],
    "template": {
        "settings": {"number_of_shards": 1, "number_of_replicas": 0},
        "mappings": {
            "dynamic_templates": [{"strings": {"match_mapping_type": "string", "mapping": {"type": "keyword"}}}],
            "properties": {
                "reading_ts": {"type": "date"}, "window_start": {"type": "date"}, "window_end": {"type": "date"},
                "temperature_c": {"type": "float"}, "avg_temp_c": {"type": "float"},
                "max_temp_c": {"type": "float"}, "humidity_pct": {"type": "float"},
                "door_open": {"type": "boolean"}, "alert": {"type": "boolean"},
                "message": {"type": "text"}}}}})

for pid, title, ts in [("freezer-readings", "freezer-readings-*", "reading_ts"),
                       ("freezer-window-stats", "freezer-window-stats", "window_start"),
                       ("freezer-alerts", "freezer-alerts", "window_start")]:
    call(host, auth, "POST", f"/_dashboards/api/saved_objects/index-pattern/{pid}",
         {"attributes": {"title": title, "timeFieldName": ts}}, dashboards=True)
print(f"Dashboards: https://{host}/_dashboards  (user {sec['username']}, password in Secrets Manager)")
