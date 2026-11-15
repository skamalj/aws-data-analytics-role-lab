"""
Render the engineers' MCP client configuration for the official AWS Labs PostgreSQL MCP server.
Placeholders ({{CLUSTER_ARN}}, {{REGION}}, {{ADMIN_SECRET_ARN}}, {{APP_SECRET_ARN}}, {{DIAG_SECRET_ARN}}) come from
the base stack. Output: awslabs/mcp.generated.json - paste it into Claude Code (.mcp.json), Kiro, Amazon Q CLI, ...

    python3 missions/D4-mcp-diagnostics/awslabs/render.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "common"))
from dbsql import base_outputs  # noqa: E402

o = base_outputs()
text = open(os.path.join(HERE, "mcp.template.json")).read()
for k, v in {"CLUSTER_ARN": o["cluster_arn"], "REGION": o["region"], "ADMIN_SECRET_ARN": o["admin_secret_arn"],
             "APP_SECRET_ARN": o["app_secret_arn"], "DIAG_SECRET_ARN": o["diag_secret_arn"]}.items():
    text = text.replace("{{" + k + "}}", v)
json.loads(text)
open(os.path.join(HERE, "mcp.generated.json"), "w").write(text)
print(f"wrote {os.path.join(HERE, 'mcp.generated.json')}")
