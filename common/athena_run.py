"""
Run one or more Athena statements from a file (each ending with ';' at end of line) or from the
command line, wait for each to finish and print the result as a table.

    python3 common/athena_run.py --workgroup cq-da-01 --file solutions/01-data-lakes/queries.sql
    python3 common/athena_run.py --workgroup cq-da-01 --sql "SELECT 1"
    python3 common/athena_run.py --workgroup cq-da-01 --sql "..." --catalog dynamo_catalog
"""
import argparse
import re
import time

import boto3


def split_sql(text):
    """Statements end with ';' at the end of a line. Full-line '--' comments are dropped."""
    text = "\n".join(l for l in text.splitlines() if not l.strip().startswith("--"))
    return [s.strip() for s in re.split(r";[ \t]*(?:\n|$)", text) if s.strip()]


def run(athena, sql, workgroup, catalog=None, database=None):
    kw = {"QueryString": sql, "WorkGroup": workgroup}
    ctx = {}
    if catalog:
        ctx["Catalog"] = catalog
    if database:
        ctx["Database"] = database
    if ctx:
        kw["QueryExecutionContext"] = ctx
    qid = athena.start_query_execution(**kw)["QueryExecutionId"]
    while True:
        q = athena.get_query_execution(QueryExecutionId=qid)["QueryExecution"]
        state = q["Status"]["State"]
        if state in ("SUCCEEDED", "FAILED", "CANCELLED"):
            break
        time.sleep(1)
    scanned = q.get("Statistics", {}).get("DataScannedInBytes", 0)
    print(f"\n-- {sql.splitlines()[0][:100]}  [{state}, scanned {scanned:,} bytes]")
    if state != "SUCCEEDED":
        print("   ", q["Status"].get("StateChangeReason"))
        return False
    pages = athena.get_paginator("get_query_results").paginate(QueryExecutionId=qid)
    rows = [[c.get("VarCharValue", "") for c in r["Data"]] for p in pages for r in p["ResultSet"]["Rows"]]
    if rows:
        widths = [max(len(r[i]) if i < len(r) else 0 for r in rows[:50]) for i in range(len(rows[0]))]
        for r in rows[:50]:
            print("   " + " | ".join(v.ljust(w) for v, w in zip(r, widths)))
        if len(rows) > 50:
            print(f"   ... {len(rows) - 50} more rows")
    return True


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--workgroup", required=True)
    ap.add_argument("--file")
    ap.add_argument("--sql")
    ap.add_argument("--catalog")
    ap.add_argument("--database")
    a = ap.parse_args()
    text = open(a.file).read() if a.file else a.sql
    client = boto3.client("athena")
    ok = all([run(client, s, a.workgroup, a.catalog, a.database) for s in split_sql(text)])
    raise SystemExit(0 if ok else 1)
