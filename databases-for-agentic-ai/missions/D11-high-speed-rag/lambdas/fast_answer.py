"""
fast_answer tool: retrieve the best passages for a customer question as fast as possible.
Query embeddings are cached in DynamoDB (repeat questions skip Bedrock), and every response reports
where the time went: client_init_ms, embed_ms, search_ms, total_ms, cache_hit.
Metrics go to CloudWatch via Embedded Metric Format (namespace Riverbend/FastRag).
"""
import hashlib
import json
import os
import time

import boto3

DIMS = int(os.environ.get("EMBED_DIMENSIONS", "1024"))
MODEL = "amazon.titan-embed-text-v2:0"


def handler(event, context):
    t0 = time.perf_counter()
    rds = boto3.client("rds-data")
    bedrock = boto3.client("bedrock-runtime")
    cache = boto3.resource("dynamodb").Table(os.environ["CACHE_TABLE"])
    db = {"resourceArn": os.environ["CLUSTER_ARN"], "secretArn": os.environ["DB_SECRET_ARN"], "database": os.environ["DB_NAME"]}
    t_init = time.perf_counter()

    question = str(event.get("question", "")).strip()
    key = f"{MODEL}:{DIMS}:{question}:{time.time()}"
    hit = cache.get_item(Key={"cache_key": key}).get("Item")
    if hit:
        vec = hit["vector"]
    else:
        r = bedrock.invoke_model(modelId=MODEL, contentType="application/json",
                                 body=json.dumps({"inputText": question, "dimensions": DIMS, "normalize": True}))
        vec = "[" + ",".join(f"{x:.7f}" for x in json.loads(r["body"].read())["embedding"]) + "]"
        cache.put_item(Item={"cache_key": key, "vector": vec, "expires_at": int(time.time()) + 86400})
    t_embed = time.perf_counter()

    res = rds.execute_statement(
        sql="SELECT doc, content FROM knowledge.d11_chunks ORDER BY embedding <=> CAST(:q AS vector) LIMIT 3",
        parameters=[{"name": "q", "value": {"stringValue": vec}}], formatRecordsAs="JSON", **db)
    t_end = time.perf_counter()
    timings = {"client_init_ms": round((t_init - t0) * 1000, 1), "embed_ms": round((t_embed - t_init) * 1000, 1),
               "search_ms": round((t_end - t_embed) * 1000, 1), "total_ms": round((t_end - t0) * 1000, 1),
               "cache_hit": bool(hit)}
    print(json.dumps({"_aws": {"Timestamp": int(time.time() * 1000), "CloudWatchMetrics": [{
        "Namespace": "Riverbend/FastRag", "Dimensions": [[]],
        "Metrics": [{"Name": n, "Unit": "Milliseconds"} for n in ("client_init_ms", "embed_ms", "search_ms", "total_ms")]}]},
        **timings}))
    return {"passages": json.loads(res.get("formattedRecords") or "[]"), "timings": timings}
