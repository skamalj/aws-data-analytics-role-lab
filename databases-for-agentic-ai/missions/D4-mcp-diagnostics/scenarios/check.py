"""Grading entry point for D4: Part A audit, plus Part B if the AWS Labs MCP config has been rendered."""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
failed = subprocess.run([sys.executable, os.path.join(HERE, "audit.py")]).returncode != 0
if os.path.exists(os.path.join(HERE, "..", "awslabs", "mcp.generated.json")):
    print("\n### Part B: AWS Labs PostgreSQL MCP server")
    failed |= subprocess.run([sys.executable, os.path.join(HERE, "check_awslabs.py")]).returncode != 0
else:
    print("\n(Part B skipped: run awslabs/render.py to include it)")
sys.exit(1 if failed else 0)
