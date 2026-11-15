"""
Document ingestion for Trail Desk's pgvector store (triggered by EventBridge "Object Created" events).
Reads the uploaded document, splits it into chunks, embeds each chunk with Titan Text Embeddings V2
and stores the chunks in knowledge.d9_chunks (as bedrock_kb_user via the RDS Data API).
"""
import json
import os
import urllib.parse

import boto3

s3 = boto3.client("s3")
rds = boto3.client("rds-data")
bedrock = boto3.client("bedrock-runtime")
DB = {"resourceArn": os.environ["CLUSTER_ARN"], "secretArn": os.environ["DB_SECRET_ARN"], "database": os.environ["DB_NAME"]}
CHUNK_CHARS = int(os.environ.get("CHUNK_CHARS", "60000"))
OVERLAP = int(os.environ.get("CHUNK_OVERLAP", "0"))


def chunks(text):
    step = max(1, CHUNK_CHARS - OVERLAP)
    return [text[i:i + CHUNK_CHARS] for i in range(0, len(text), step) if text[i:i + CHUNK_CHARS].strip()]


def embed(text):
    r = bedrock.invoke_model(modelId="amazon.titan-embed-text-v2:0", contentType="application/json",
                             body=json.dumps({"inputText": text, "dimensions": 1024, "normalize": True}))
    return "[" + ",".join(f"{x:.7f}" for x in json.loads(r["body"].read())["embedding"]) + "]"


def handler(event, context):
    bucket = event["detail"]["bucket"]["name"]
    key = urllib.parse.unquote_plus(event["detail"]["object"]["key"])
    text = s3.get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8")
    parts = chunks(text)
    for n, part in enumerate(parts):
        rds.execute_statement(
            sql="INSERT INTO knowledge.d9_chunks (doc_key, chunk_no, content, embedding, source_uri) "
                "VALUES (:k, :n, :c, CAST(:v AS vector), :u)",
            parameters=[{"name": "k", "value": {"stringValue": key}}, {"name": "n", "value": {"longValue": n}},
                        {"name": "c", "value": {"stringValue": part}}, {"name": "v", "value": {"stringValue": embed(part)}},
                        {"name": "u", "value": {"stringValue": f"s3://{bucket}/{key}"}}], **DB)
    print(json.dumps({"ingested": key, "chunks": len(parts), "chars": len(text)}))
    return {"doc": key, "chunks": len(parts)}
