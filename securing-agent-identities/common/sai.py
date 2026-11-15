"""
Shared helpers for the Securing Agent Identities challenges: terraform outputs, Cognito tokens,
invoking runtimes with a JWT (HTTPS) or SigV4 (boto3), assuming persona roles, PASS/FAIL checks.
"""
import base64
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid

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


def session(role_arn=None, region=None, tags=None):
    region = region or base()["region"]
    if not role_arn:
        return boto3.Session(region_name=region)
    c = boto3.client("sts").assume_role(RoleArn=role_arn, RoleSessionName="larchmont-check")["Credentials"]
    return boto3.Session(aws_access_key_id=c["AccessKeyId"], aws_secret_access_key=c["SecretAccessKey"],
                         aws_session_token=c["SessionToken"], region_name=region)


def token(token_url, client_id, client_secret, scope):
    """Client-credentials token from Cognito. Returns (access_token, error)."""
    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    data = urllib.parse.urlencode({"grant_type": "client_credentials", "scope": scope}).encode()
    req = urllib.request.Request(token_url, data=data, method="POST",
                                 headers={"Authorization": f"Basic {basic}", "Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())["access_token"], None
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code} {e.read().decode()[:200]}"


def claims(tok):
    part = tok.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))


def sid():
    return f"larchmont-{uuid.uuid4()}"          # runtime session ids must be >= 33 characters


def invoke_jwt(runtime_arn, tok, payload):
    """Returns (http_status, body)."""
    region = runtime_arn.split(":")[3]
    url = f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{urllib.parse.quote(runtime_arn, safe='')}/invocations?qualifier=DEFAULT"
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST", headers={
        "Authorization": f"Bearer {tok}", "Content-Type": "application/json", "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": sid()})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:300]
    except Exception as e:  # noqa: BLE001
        return 0, f"{type(e).__name__}: {e}"


def invoke_sigv4(sess, runtime_arn, payload, user_id=None):
    """Returns (ok, body_or_error)."""
    c = sess.client("bedrock-agentcore")
    kw = {"agentRuntimeArn": runtime_arn, "runtimeSessionId": sid(), "qualifier": "DEFAULT", "payload": json.dumps(payload).encode()}
    if user_id:
        kw["runtimeUserId"] = user_id
    try:
        return True, json.loads(c.invoke_agent_runtime(**kw)["response"].read())
    except Exception as e:  # noqa: BLE001
        code = getattr(e, "response", {}).get("Error", {}).get("Code", type(e).__name__)
        return False, f"{code}: {str(e)[:250]}"


def check(name, ok, detail=""):
    _results.append(bool(ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  -- {detail}" if detail else ""), flush=True)
    return ok


def safe(fn, *a, **kw):
    try:
        return fn(*a, **kw), None
    except Exception as e:  # noqa: BLE001
        code = getattr(e, "response", {}).get("Error", {}).get("Code", type(e).__name__)
        return None, f"{code}: {str(e)[:250]}"


def denied(err):
    return bool(err) and any(k in err for k in ("AccessDenied", "UnauthorizedOperation", "not authorized", "Forbidden"))


def finish():
    print(f"\n{sum(_results)}/{len(_results)} checks passed")
    sys.exit(0 if _results and all(_results) else 1)
