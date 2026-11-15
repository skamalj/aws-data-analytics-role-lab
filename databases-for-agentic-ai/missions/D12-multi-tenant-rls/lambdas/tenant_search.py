"""
tenant_search tool for Riverbend's multi-tenant document service.
tenant_id comes from the caller's authenticated context (the API layer), never from the model.
Isolation is enforced by PostgreSQL row-level security on saas.tenant_docs via app.tenant_id.
"""
import json
import os

import boto3

rds = boto3.client("rds-data")
DB = {"resourceArn": os.environ["CLUSTER_ARN"], "secretArn": os.environ["DB_SECRET_ARN"], "database": os.environ["DB_NAME"]}


def handler(event, context):
    tenant = str(event["tenant_id"])
    doc_id = int(event["doc_id"])          # "more like this document"
    k = max(1, min(int(event.get("k", 10)), 50))
    rds.execute_statement(sql="SELECT set_config('app.tenant_id', :t, false)",
                          parameters=[{"name": "t", "value": {"stringValue": tenant}}], **DB)
    r = rds.execute_statement(
        sql="SELECT id, tenant_id, title FROM saas.tenant_docs "
            "ORDER BY embedding <=> (SELECT embedding FROM saas.tenant_docs WHERE id = :id) LIMIT :k",
        parameters=[{"name": "id", "value": {"longValue": doc_id}}, {"name": "k", "value": {"longValue": k}}],
        formatRecordsAs="JSON", **DB)
    return {"tenant_id": tenant, "results": json.loads(r.get("formattedRecords") or "[]")}
