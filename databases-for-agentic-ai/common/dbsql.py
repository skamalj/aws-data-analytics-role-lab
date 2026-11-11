"""
Run SQL against the shared Aurora PostgreSQL cluster through the RDS Data API.

    python3 common/dbsql.py --file missions/D1-structured-data/db/grants.sql      # as the admin user
    python3 common/dbsql.py --sql "SELECT count(*) FROM commerce.orders"
    python3 common/dbsql.py --as app --sql "SELECT current_user"                   # as trail_desk_app

Connection details come from `terraform output` of base/terraform. Statements are split on ';' at the
end of a line, except inside $$ ... $$ blocks. Placeholders {{APP_PASSWORD}} etc. are filled from the
base stack's secrets (used by the base seed only).
"""
import argparse
import json
import os
import subprocess
import sys
import time

import boto3

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECRETS = {"admin": "admin_secret_arn", "app": "app_secret_arn", "kb": "kb_secret_arn", "diag": "diag_secret_arn"}


def base_outputs():
    r = subprocess.run(["terraform", f"-chdir={ROOT}/base/terraform", "output", "-json"], capture_output=True, text=True)
    if r.returncode:
        sys.exit("base stack not deployed? run ./scripts/deploy.sh base\n" + r.stderr)
    return {k: v["value"] for k, v in json.loads(r.stdout).items()}


def split_sql(text):
    out, cur, in_dollar = [], [], False
    for line in text.splitlines():
        if line.strip().startswith("--") and not in_dollar:
            continue
        if line.count("$$") % 2:
            in_dollar = not in_dollar
        cur.append(line)
        if not in_dollar and line.rstrip().endswith(";"):
            out.append("\n".join(cur).strip().rstrip(";"))
            cur = []
    if "\n".join(cur).strip():
        out.append("\n".join(cur).strip())
    return [s for s in out if s]


class Db:
    def __init__(self, who="admin", out=None):
        self.o = out or base_outputs()
        self.c = boto3.client("rds-data", region_name=self.o["region"])
        self.kw = {"resourceArn": self.o["cluster_arn"], "secretArn": self.o[SECRETS[who]], "database": self.o["database"]}

    def run(self, sql, params=None, retries=12):
        for i in range(retries):
            try:
                return self.c.execute_statement(sql=sql, includeResultMetadata=True,
                                                parameters=params or [], **self.kw)
            except self.c.exceptions.DatabaseResumingException:
                print("  (database is resuming from auto-pause, waiting 10 s)", flush=True)
                time.sleep(10)
            except self.c.exceptions.BadRequestException as e:
                if "resuming" in str(e).lower() or "Communications link failure" in str(e):
                    time.sleep(10)
                    continue
                raise
        raise RuntimeError("database did not resume")

    def run_file(self, path, subst=None, quiet=False):
        text = open(path).read()
        for k, v in (subst or {}).items():
            text = text.replace("{{" + k + "}}", v)
        for stmt in split_sql(text):
            r = self.run(stmt)
            if not quiet:
                print(f"  ok: {stmt.splitlines()[0][:90]}")
        return True


def show(resp):
    cols = [c["name"] for c in resp.get("columnMetadata", [])]
    rows = [[str(list(v.values())[0]) if not v.get("isNull") else "NULL" for v in r] for r in resp.get("records", [])]
    if not cols:
        print(f"  {resp.get('numberOfRecordsUpdated', 0)} rows affected")
        return
    table = [cols] + rows[:50]
    w = [max(len(r[i]) for r in table) for i in range(len(cols))]
    for r in table:
        print("  " + " | ".join(v.ljust(x) for v, x in zip(r, w)))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--file")
    ap.add_argument("--sql")
    ap.add_argument("--as", dest="who", default="admin", choices=list(SECRETS))
    a = ap.parse_args()
    db = Db(a.who)
    try:
        if a.file:
            db.run_file(a.file)
        else:
            for s in split_sql(a.sql if a.sql.rstrip().endswith(";") else a.sql + ";"):
                show(db.run(s))
    except Exception as e:
        sys.exit(f"{type(e).__name__}: {e}")
