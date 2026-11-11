"""
Talk to a mission's agent, exactly as the Riverbend web console would.

    python3 common/chat.py M1 "Hi, what can you help me with?"
    python3 common/chat.py M4 "I prefer tents under 2 kg" --actor alex --new-session
    python3 common/chat.py M1 --show-token            # decode the access token's claims

Connection details come from the mission's `terraform output`. Missions whose runtime uses a
JWT authorizer get an OAuth token from Amazon Cognito (client credentials) and call the runtime's
HTTPS endpoint with it; the others call InvokeAgentRuntime with your AWS (SigV4) credentials.
The session id is kept in .session-<mission> so follow-up questions continue the same session.
"""
import argparse
import base64
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def tf_outputs(mission):
    folder = next((os.path.join(ROOT, "missions", d, "terraform") for d in sorted(os.listdir(os.path.join(ROOT, "missions")))
                   if d.upper().startswith(mission.upper())), None)
    if not folder:
        sys.exit(f"no mission folder starting with {mission}")
    raw = subprocess.run(["terraform", f"-chdir={folder}", "output", "-json"], capture_output=True, text=True)
    if raw.returncode:
        sys.exit(f"terraform output failed in {folder}:\n{raw.stderr}")
    return {k: v["value"] for k, v in json.loads(raw.stdout).items()}


def session_id(mission, new):
    f = os.path.join(ROOT, f".session-{mission.upper()}")
    if new or not os.path.exists(f):
        with open(f, "w") as fh:
            fh.write(f"riverbend-{uuid.uuid4()}")   # runtime session ids must be >= 33 characters
    return open(f).read().strip()


def get_token(o):
    basic = base64.b64encode(f"{o['client_id']}:{o['client_secret']}".encode()).decode()
    data = urllib.parse.urlencode({"grant_type": "client_credentials", "scope": o["requested_scope"]}).encode()
    req = urllib.request.Request(o["token_url"], data=data, method="POST",
                                 headers={"Authorization": f"Basic {basic}",
                                          "Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())["access_token"]
    except urllib.error.HTTPError as e:
        sys.exit(f"[token] Cognito refused the token request: HTTP {e.code} {e.read().decode()}")


def claims(token):
    part = token.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))


def invoke_jwt(o, payload, sid):
    token = get_token(o)
    region = o["runtime_arn"].split(":")[3]
    url = (f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/"
           f"{urllib.parse.quote(o['runtime_arn'], safe='')}/invocations?qualifier=DEFAULT")
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST", headers={
        "Authorization": f"Bearer {token}", "Content-Type": "application/json",
        "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": sid})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"[runtime] HTTP {e.code}: {e.read().decode()}")


def invoke_iam(o, payload, sid):
    import boto3
    region = o["runtime_arn"].split(":")[3]
    c = boto3.client("bedrock-agentcore", region_name=region)
    try:
        r = c.invoke_agent_runtime(agentRuntimeArn=o["runtime_arn"], runtimeSessionId=sid,
                                   qualifier="DEFAULT", payload=json.dumps(payload).encode())
    except Exception as e:
        sys.exit(f"[runtime] {type(e).__name__}: {e}")
    return json.loads(r["response"].read())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mission", help="M1 .. M6")
    ap.add_argument("prompt", nargs="?")
    ap.add_argument("--actor", help="customer id the agent should remember you as (mission 4)")
    ap.add_argument("--new-session", action="store_true", help="start a fresh runtime session")
    ap.add_argument("--show-token", action="store_true", help="print the decoded access token claims")
    ap.add_argument("--raw", action="store_true", help="print the full JSON response")
    a = ap.parse_args()
    o = tf_outputs(a.mission)
    if a.show_token:
        print(json.dumps(claims(get_token(o)), indent=2))
        return
    if not a.prompt:
        ap.error("prompt is required")
    payload = {"prompt": a.prompt}
    if a.actor:
        payload["actor_id"] = a.actor
    sid = session_id(a.mission, a.new_session)
    res = invoke_jwt(o, payload, sid) if o.get("auth_mode") == "jwt" else invoke_iam(o, payload, sid)
    if a.raw or "error" in res:
        print(json.dumps(res, indent=2))
    else:
        print(res.get("answer", ""))
        for t in res.get("tools_used", []):
            print(f"  [tool] {t['tool']} {json.dumps(t['input'])}")
        for t in res.get("trace", []):
            print(f"  [trace] {json.dumps(t)}")


if __name__ == "__main__":
    main()
