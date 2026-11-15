"""Titan Text Embeddings V2 helper used by the ingestion / benchmark scripts."""
import json
import os

import boto3

MODEL = os.environ.get("EMBED_MODEL_ID", "amazon.titan-embed-text-v2:0")
_client = None


def embed(text, dimensions=1024, region=None):
    global _client
    if _client is None:
        _client = boto3.client("bedrock-runtime", region_name=region or os.environ.get("AWS_REGION"))
    body = {"inputText": text, "dimensions": int(dimensions), "normalize": True}
    r = _client.invoke_model(modelId=MODEL, body=json.dumps(body), contentType="application/json", accept="application/json")
    return json.loads(r["body"].read())["embedding"]


def to_pgvector(vec):
    return "[" + ",".join(f"{x:.7f}" for x in vec) + "]"


def chunk_markdown(text, target_chars=900):
    """Split on blank lines, then merge paragraphs up to ~target_chars (keeps headings with their text)."""
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks, cur = [], ""
    for p in paras:
        if cur and len(cur) + len(p) > target_chars:
            chunks.append(cur)
            cur = p
        else:
            cur = f"{cur}\n\n{p}" if cur else p
    if cur:
        chunks.append(cur)
    return chunks
