"""search_docs tool (AgentCore Gateway Lambda target): semantic search over knowledge.doc_chunks with pgvector."""
import json
import os

import boto3

rds = boto3.client("rds-data")
bedrock = boto3.client("bedrock-runtime")
DB = {"resourceArn": os.environ["CLUSTER_ARN"], "secretArn": os.environ["DB_SECRET_ARN"], "database": os.environ["DB_NAME"]}
DIMS = int(os.environ.get("EMBED_DIMENSIONS", "1024"))


def embed(text):
    r = bedrock.invoke_model(modelId="amazon.titan-embed-text-v2:0", contentType="application/json",
                             body=json.dumps({"inputText": text, "dimensions": DIMS, "normalize": True}))
    return "[" + ",".join(f"{x:.7f}" for x in json.loads(r["body"].read())["embedding"]) + "]"


def search_docs(args):
    q = str(args.get("query", "")).strip()[:2000]
    if not q:
        return {"error": "query is required"}
    r = rds.execute_statement(
        sql="SELECT doc, chunk_no, content, round((1 - (embedding <=> CAST(:q AS vector)))::numeric, 3) AS score "
            "FROM knowledge.doc_chunks ORDER BY embedding <=> CAST(:q AS vector) LIMIT 4",
        parameters=[{"name": "q", "value": {"stringValue": embed(q)}}], formatRecordsAs="JSON", **DB)
    hits = json.loads(r.get("formattedRecords") or "[]")
    return {"passages": hits} if hits else {"passages": [], "note": "no documents indexed"}


def handler(event, context):
    tool = context.client_context.custom["bedrockAgentCoreToolName"].split("___", 1)[-1]
    print(json.dumps({"tool": tool, "arguments": event}))
    try:
        return search_docs(event) if tool == "search_docs" else {"error": f"unknown tool {tool}"}
    except Exception as e:
        print(f"ERROR {type(e).__name__}: {e}")
        return {"error": f"{type(e).__name__}: {e}"}
