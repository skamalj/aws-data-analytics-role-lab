"""
Run SQL statements against Amazon Redshift Serverless through the Redshift Data API.
Statements end with ';' at the end of a line, as in athena_run.py.

    python3 common/redshift_run.py --workgroup cq-da-07 --database riverbend \
        --secret-arn arn:aws:secretsmanager:... --file solutions/07-cloud-data-warehouse/01_schema.sql
"""
import argparse
import time

import boto3

from athena_run import split_sql


def run(client, sql, workgroup, database, secret_arn):
    sid = client.execute_statement(WorkgroupName=workgroup, Database=database,
                                   SecretArn=secret_arn, Sql=sql)["Id"]
    while True:
        d = client.describe_statement(Id=sid)
        if d["Status"] in ("FINISHED", "FAILED", "ABORTED"):
            break
        time.sleep(1)
    print(f"\n-- {sql.splitlines()[0][:100]}  [{d['Status']}, {d.get('Duration', 0) / 1e9:.1f}s]")
    if d["Status"] != "FINISHED":
        print("   ", d.get("Error"))
        return False
    if d.get("HasResultSet"):
        res = client.get_statement_result(Id=sid)
        cols = [c["name"] for c in res["ColumnMetadata"]]
        rows = [[str(list(v.values())[0]) if v and not v.get("isNull") else "NULL" for v in r]
                for r in res["Records"]]
        table = [cols] + rows[:50]
        widths = [max(len(r[i]) for r in table) for i in range(len(cols))]
        for r in table:
            print("   " + " | ".join(v.ljust(w) for v, w in zip(r, widths)))
    elif d.get("ResultRows", -1) >= 0:
        print(f"    {d['ResultRows']} rows affected")
    return True


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--workgroup", required=True)
    ap.add_argument("--database", required=True)
    ap.add_argument("--secret-arn", required=True)
    ap.add_argument("--file")
    ap.add_argument("--sql")
    a = ap.parse_args()
    text = open(a.file).read() if a.file else a.sql
    c = boto3.client("redshift-data")
    ok = all([run(c, s, a.workgroup, a.database, a.secret_arn) for s in split_sql(text)])
    raise SystemExit(0 if ok else 1)
