"""
Shared helpers for the lakehouse challenges: terraform outputs, Athena queries, Glue job runs,
PASS/FAIL checks, and assuming persona roles.
"""
import json
import os
import subprocess
import sys
import time

import boto3

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_results = []


def tf_outputs(folder):
    r = subprocess.run(["terraform", f"-chdir={folder}", "output", "-json"], capture_output=True, text=True)
    out = {k: v["value"] for k, v in json.loads(r.stdout or "{}").items()}
    if not out:
        sys.exit(f"no terraform outputs in {folder} - deploy it first")
    return out


def base():
    return tf_outputs(os.path.join(ROOT, "base", "terraform"))


def mission(mission_dir):
    return tf_outputs(os.path.join(mission_dir, "terraform"))


def session(role_arn=None, region=None):
    region = region or base()["region"]
    if not role_arn:
        return boto3.Session(region_name=region)
    c = boto3.client("sts").assume_role(RoleArn=role_arn, RoleSessionName="riverbend-check")["Credentials"]
    return boto3.Session(aws_access_key_id=c["AccessKeyId"], aws_secret_access_key=c["SecretAccessKey"],
                         aws_session_token=c["SessionToken"], region_name=region)


class Athena:
    def __init__(self, sess=None, workgroup=None):
        b = base()
        self.wg = workgroup or b["athena_workgroup"]
        self.c = (sess or session()).client("athena")

    def run(self, sql, wait=True):
        qid = self.c.start_query_execution(QueryString=sql, WorkGroup=self.wg)["QueryExecutionId"]
        if not wait:
            return qid
        while True:
            q = self.c.get_query_execution(QueryExecutionId=qid)["QueryExecution"]
            if q["Status"]["State"] in ("SUCCEEDED", "FAILED", "CANCELLED"):
                break
            time.sleep(1)
        if q["Status"]["State"] != "SUCCEEDED":
            raise RuntimeError(q["Status"].get("StateChangeReason", q["Status"]["State"]))
        return q

    def rows(self, sql):
        q = self.run(sql)
        pages = self.c.get_paginator("get_query_results").paginate(QueryExecutionId=q["QueryExecutionId"])
        data = [[c.get("VarCharValue") for c in r["Data"]] for p in pages for r in p["ResultSet"]["Rows"]]
        return [dict(zip(data[0], r)) for r in data[1:]] if data else []

    def stats(self, sql):
        s = self.run(sql)["Statistics"]
        return {"engine_ms": s.get("EngineExecutionTimeInMillis", 0), "total_ms": s.get("TotalExecutionTimeInMillis", 0),
                "scanned": s.get("DataScannedInBytes", 0)}

    def run_file(self, path, subst=None):
        text = open(path).read()
        for k, v in (subst or {}).items():
            text = text.replace("{{" + k + "}}", v)
        stmts = [s.strip() for s in "\n".join(l for l in text.splitlines() if not l.strip().startswith("--")).split(";\n") if s.strip()]
        for s in stmts:
            s = s.rstrip(";")
            self.run(s)
            print(f"  ok: {s.splitlines()[0][:90]}")


def run_glue(job, args, region=None):
    g = session(region=region).client("glue")
    rid = g.start_job_run(JobName=job, Arguments=args)["JobRunId"]
    print(f"  {job} {json.dumps(args)} -> run {rid}", end="", flush=True)
    while True:
        r = g.get_job_run(JobName=job, RunId=rid)["JobRun"]
        if r["JobRunState"] in ("SUCCEEDED", "FAILED", "ERROR", "TIMEOUT", "STOPPED"):
            break
        print(".", end="", flush=True)
        time.sleep(15)
    print(f" {r['JobRunState']}" + (f": {r.get('ErrorMessage', '')[:300]}" if r["JobRunState"] != "SUCCEEDED" else ""))
    return r


def check(name, ok, detail=""):
    _results.append(bool(ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  -- {detail}" if detail else ""), flush=True)
    return ok


def safe(fn, *a, **kw):
    try:
        return fn(*a, **kw), None
    except Exception as e:  # noqa: BLE001
        return None, f"{type(e).__name__}: {str(e)[:300]}"


def finish():
    print(f"\n{sum(_results)}/{len(_results)} checks passed")
    sys.exit(0 if _results and all(_results) else 1)
