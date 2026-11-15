"""
Notebook helpers for the Graph Memory Agent lab.

    import labkit                      # moves to the project root, loads .env, makes `src` importable
    labkit.reload("memory_client", "mcp_server")   # pick up your edits to src/*.py (in dependency order)
    labkit.upload("mcp_tools_result.json")         # = aws s3 cp <file> s3://$EVIDENCE_BUCKET/evidence/<file>
    labkit.show("src/memory_client.py", "def get_session")   # print the code around a marker
"""
import importlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)                                    # src.* and the evidence files live relative to the root
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from dotenv import load_dotenv  # noqa: E402

if not os.path.exists(os.path.join(ROOT, ".env")):
    raise RuntimeError("No .env in the project root: run `python scripts/make_env.py` (see notebook 00).")
load_dotenv(os.path.join(ROOT, ".env"), override=True)

import boto3  # noqa: E402

REGION = os.environ.get("AWS_REGION", "us-east-1")
BUCKET = os.environ.get("EVIDENCE_BUCKET", "")
PREFIX = os.environ.get("EVIDENCE_PREFIX", "evidence")


def reload(*modules):
    """Re-import src modules after you edit them. Order matters: reload a module before the ones that import it."""
    out = []
    for name in modules:
        full = name if name.startswith("src.") else f"src.{name}"
        mod = sys.modules.get(full)
        out.append(importlib.reload(mod) if mod else importlib.import_module(full))
        print(f"reloaded {full}")
    return out[0] if len(out) == 1 else out


def upload(filename):
    """Publish one evidence file to s3://$EVIDENCE_BUCKET/$EVIDENCE_PREFIX/<filename>."""
    if not BUCKET:
        raise RuntimeError("EVIDENCE_BUCKET is not set in .env")
    key = f"{PREFIX}/{os.path.basename(filename)}"
    boto3.client("s3", region_name=REGION).upload_file(filename, BUCKET, key)
    print(f"uploaded {filename} -> s3://{BUCKET}/{key}")
    return f"s3://{BUCKET}/{key}"


def show(path, marker, before=2, after=25):
    """Print the lines of a source file around the first line containing `marker`."""
    lines = open(os.path.join(ROOT, path)).read().splitlines()
    idx = next((i for i, l in enumerate(lines) if marker in l), None)
    if idx is None:
        print(f"'{marker}' not found in {path}")
        return
    for i in range(max(0, idx - before), min(len(lines), idx + after)):
        print(f"{i + 1:4d}  {lines[i]}")


def pretty(obj):
    """Pretty-print JSON strings (MCP tool results) or Python objects."""
    if isinstance(obj, str):
        try:
            obj = json.loads(obj)
        except json.JSONDecodeError:
            print(obj)
            return
    print(json.dumps(obj, indent=2, default=str))


def grade(*goals):
    """Run the local grader for the given goals (it reads your uploaded evidence from S3)."""
    import subprocess
    subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "check_evidence.py"), *map(str, goals)], cwd=ROOT)
