"""
partner_search tool: knowledge-base search for a partner shop's customers.
The partner (tenant) comes from the authenticated request context - the API layer puts it in
event["context"]["tenant_id"]; the model only supplies event["args"]["query"].
"""
import json
import os

import boto3

kb = boto3.client("bedrock-agent-runtime")


def handler(event, context):
    args = event.get("args", {})
    tenant = args.get("tenant_id") or event.get("context", {}).get("tenant_id")
    r = kb.retrieve(
        knowledgeBaseId=os.environ["KB_ID"],
        retrievalQuery={"text": str(args.get("query", ""))},
        retrievalConfiguration={"vectorSearchConfiguration": {
            "numberOfResults": 4,
            "filter": {"equals": {"key": "tenant", "value": tenant}},
        }})
    hits = [{"text": x["content"]["text"][:300], "source": x["location"]["s3Location"]["uri"],
             "tenant_id": (x.get("metadata") or {}).get("tenant_id")} for x in r["retrievalResults"]]
    return {"tenant_id": tenant, "results": hits}
