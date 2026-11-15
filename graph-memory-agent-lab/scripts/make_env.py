"""
Write the lab's .env (project root) from the Terraform outputs plus your local Neo4j settings.

    python scripts/make_env.py                       # Aurora + OpenSearch Serverless from Terraform
    python scripts/make_env.py --local-postgres      # use a local PostgreSQL with pgvector instead of Aurora

Neo4j settings come from the environment if set (NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD), otherwise you're asked.
An existing .env is backed up to .env.bak first.
"""
import argparse
import getpass
import json
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TF = os.path.join(ROOT, "infra", "terraform")


def tf_outputs():
    r = subprocess.run(["terraform", f"-chdir={TF}", "output", "-json"], capture_output=True, text=True)
    out = {k: v["value"] for k, v in json.loads(r.stdout or "{}").items()}
    if not out:
        sys.exit("No Terraform outputs found: run `terraform -chdir=infra/terraform apply` first.")
    return out


def ask(name, default=None, secret=False):
    if os.getenv(name):
        return os.environ[name]
    prompt = f"{name}" + (f" [{default}]" if default else "") + ": "
    val = getpass.getpass(prompt) if secret else input(prompt)
    return val or default or ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--local-postgres", action="store_true", help="point PG* at a local PostgreSQL + pgvector")
    a = ap.parse_args()
    o = tf_outputs()

    env = {
        "# AWS": None,
        "AWS_REGION": o["region"],
        "BEDROCK_EMBEDDING_MODEL_ID": "amazon.titan-embed-text-v2:0",
        "BEDROCK_LLM_MODEL_ID": "us.amazon.nova-pro-v1:0",
        "EMBEDDING_DIMENSIONS": "1024",
        "SESSION_TABLE": o["session_table"],
        "EVIDENCE_BUCKET": o["evidence_bucket"],
        "EVIDENCE_PREFIX": "evidence",
        "MCP_VECTOR_ROLE_NAME": o["mcp_vector_role_name"],
        "SESSION_TABLE_ARN": o["session_table_arn"],
        "# OpenSearch Serverless (SigV4 with your credentials)": None,
        "OPENSEARCH_HOST": o["opensearch_endpoint"].replace("https://", ""),
        "OPENSEARCH_PORT": "443",
        "OPENSEARCH_USE_SIGV4": "true",
        "OPENSEARCH_SERVICE": "aoss",
        "OPENSEARCH_ENGINE": "faiss",
        "# Neo4j (local)": None,
        "NEO4J_URI": ask("NEO4J_URI", "bolt://localhost:7687"),
        "NEO4J_USER": ask("NEO4J_USER", "neo4j"),
        "NEO4J_PASSWORD": ask("NEO4J_PASSWORD", secret=True),
        "NEO4J_DATABASE": ask("NEO4J_DATABASE", "neo4j"),
    }
    if a.local_postgres:
        env.update({
            "# PostgreSQL (local, with the pgvector extension installed)": None,
            "PGHOST": ask("PGHOST", "localhost"), "PGPORT": ask("PGPORT", "5432"),
            "PGDATABASE": ask("PGDATABASE", "coa"), "PGUSER": ask("PGUSER", "postgres"),
            "PGPASSWORD": ask("PGPASSWORD", secret=True), "PGSSLMODE": ask("PGSSLMODE", "prefer"),
        })
    else:
        if not o.get("pg_host"):
            sys.exit("Terraform was applied with create_aurora=false: re-run with --local-postgres.")
        pw = subprocess.run(["terraform", f"-chdir={TF}", "output", "-raw", "pg_password"], capture_output=True, text=True).stdout
        env.update({
            "# Aurora PostgreSQL Serverless v2 (TLS required)": None,
            "PGHOST": o["pg_host"], "PGPORT": "5432", "PGDATABASE": "coa", "PGUSER": "coaadmin",
            "PGPASSWORD": pw, "PGSSLMODE": "require",
        })

    path = os.path.join(ROOT, ".env")
    if os.path.exists(path):
        shutil.copy(path, path + ".bak")
    with open(path, "w") as f:
        for k, v in env.items():
            f.write(f"\n{k}\n" if v is None else f"{k}={v}\n")
    os.chmod(path, 0o600)
    print(f"wrote {path} (permissions 600). Never commit it.")


if __name__ == "__main__":
    main()
