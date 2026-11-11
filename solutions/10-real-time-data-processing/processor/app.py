"""
Kinesis -> Lambda (60 s tumbling windows) -> Amazon OpenSearch Service.

Per invocation : index every reading into freezer-readings-YYYY.MM.DD (doc id = device+timestamp,
                 so retries overwrite instead of duplicating); send unparseable records to SQS.
Per window     : the aggregate state (count/sum/max/door-open per device) is carried between
                 invocations in event["state"]; on the final invocation of the window, write one
                 freezer-window-stats doc per device and a freezer-alerts doc when the window's
                 average temperature is above ALERT_AVG_C.
"""
import base64
import json
import os
import urllib.request

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

HOST = os.environ["OPENSEARCH_ENDPOINT"]
REGION = os.environ["AWS_REGION"]
QUEUE_URL = os.environ["FAILED_QUEUE_URL"]
ALERT_AVG_C = float(os.environ.get("ALERT_AVG_C", "-15"))
session = boto3.Session()
sqs = boto3.client("sqs")


def opensearch(method, path, body):
    url = f"https://{HOST}{path}"
    data = body.encode()
    req = AWSRequest(method=method, url=url, data=data, headers={"Content-Type": "application/x-ndjson"})
    SigV4Auth(session.get_credentials().get_frozen_credentials(), "es", REGION).add_auth(req)
    r = urllib.request.Request(url, data=data, method=method, headers=dict(req.headers.items()))
    with urllib.request.urlopen(r, timeout=25) as resp:
        return json.loads(resp.read())


def bulk(lines):
    if not lines:
        return
    res = opensearch("POST", "/_bulk", "\n".join(lines) + "\n")
    if res.get("errors"):
        first = next(i for i in res["items"] if list(i.values())[0].get("error"))
        raise RuntimeError(f"bulk indexing failed: {json.dumps(first)[:500]}")


def parse(raw):
    r = json.loads(raw)
    if not isinstance(r, dict) or not {"device_id", "reading_ts", "temperature_c"} <= r.keys():
        raise ValueError("missing fields")
    r["temperature_c"] = float(r["temperature_c"])
    return r


def dead_letter(bad):
    for i in range(0, len(bad), 10):
        sqs.send_message_batch(QueueUrl=QUEUE_URL, Entries=[
            {"Id": str(n), "MessageBody": json.dumps(b)} for n, b in enumerate(bad[i:i + 10])])


def handler(event, context):
    state = event.get("state") or {}
    lines, bad = [], []
    for rec in event.get("Records", []):
        raw = base64.b64decode(rec["kinesis"]["data"])
        try:
            r = parse(raw)
        except (ValueError, TypeError, json.JSONDecodeError) as e:
            bad.append({"reason": str(e), "sequenceNumber": rec["kinesis"]["sequenceNumber"],
                        "partitionKey": rec["kinesis"]["partitionKey"],
                        "data": raw.decode("utf-8", "replace")})
            continue
        day = r["reading_ts"][:10].replace("-", ".")
        lines.append(json.dumps({"index": {"_index": f"freezer-readings-{day}",
                                           "_id": f"{r['device_id']}-{r['reading_ts']}"}}))
        lines.append(json.dumps(r))
        s = state.setdefault(r["device_id"], {"n": 0, "sum": 0.0, "max": -999.0, "door": 0,
                                              "warehouse": r.get("warehouse")})
        s["n"] += 1
        s["sum"] += r["temperature_c"]
        s["max"] = max(s["max"], r["temperature_c"])
        s["door"] += 1 if r.get("door_open") else 0

    bulk(lines)
    dead_letter(bad)
    print(json.dumps({"records": len(event.get("Records", [])), "indexed": len(lines) // 2,
                      "dead_lettered": len(bad), "window": event.get("window"),
                      "final": event.get("isFinalInvokeForWindow", False)}))

    if not event.get("isFinalInvokeForWindow"):
        return {"state": state}

    w = event["window"]
    out = []
    for dev, s in state.items():
        avg = round(s["sum"] / s["n"], 2)
        doc = {"device_id": dev, "warehouse": s["warehouse"], "window_start": w["start"],
               "window_end": w["end"], "readings": s["n"], "avg_temp_c": avg,
               "max_temp_c": s["max"], "door_open_readings": s["door"], "alert": avg > ALERT_AVG_C}
        out.append(json.dumps({"index": {"_index": "freezer-window-stats", "_id": f"{dev}-{w['start']}"}}))
        out.append(json.dumps(doc))
        if doc["alert"]:
            out.append(json.dumps({"index": {"_index": "freezer-alerts", "_id": f"{dev}-{w['start']}"}}))
            out.append(json.dumps(dict(doc, message=f"{dev} averaged {avg} C between {w['start']} and {w['end']}")))
    bulk(out)
    return {}
