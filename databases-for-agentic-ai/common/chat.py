"""
Talk to a mission's agent the way Riverbend's web app does (SigV4 InvokeAgentRuntime).

    python3 common/chat.py D1 "Where is order O1003?"
    python3 common/chat.py D3 "I want to return order O2003" --conversation alex-1 --customer C00042
    python3 common/chat.py D3 "The reason: it's too heavy" --conversation alex-1 --new-session
    python3 common/chat.py D5 "..." --customer C00112 --raw

--conversation is the web app's stable conversation id; the runtime session id (kept in
.session-<mission>) changes whenever you pass --new-session, as when a customer comes back later.
"""
import argparse
import json
import os
import subprocess
import sys
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def tf_outputs(mission):
    mdir = next((os.path.join(ROOT, "missions", d) for d in sorted(os.listdir(os.path.join(ROOT, "missions")))
                 if d.upper().startswith(mission.upper() + "-")), None)
    if not mdir:
        sys.exit(f"no mission {mission}")
    r = subprocess.run(["terraform", f"-chdir={mdir}/terraform", "output", "-json"], capture_output=True, text=True)
    if r.returncode or r.stdout.strip() in ("", "{}"):
        sys.exit(f"mission {mission} not deployed? ./scripts/deploy.sh {mission}\n{r.stderr}")
    return {k: v["value"] for k, v in json.loads(r.stdout).items()}


def session_id(mission, new=False):
    f = os.path.join(ROOT, f".session-{mission.upper()}")
    if new or not os.path.exists(f):
        with open(f, "w") as fh:
            fh.write(f"riverbend-{uuid.uuid4()}")
    return open(f).read().strip()


def invoke(mission, payload, new_session=False, outputs=None):
    import boto3
    o = outputs or tf_outputs(mission)
    c = boto3.client("bedrock-agentcore", region_name=o["runtime_arn"].split(":")[3])
    try:
        r = c.invoke_agent_runtime(agentRuntimeArn=o["runtime_arn"], qualifier="DEFAULT",
                                   runtimeSessionId=session_id(mission, new_session),
                                   payload=json.dumps(payload).encode())
    except Exception as e:
        return {"error": f"[runtime] {type(e).__name__}: {e}"}
    return json.loads(r["response"].read())


def show(res, raw=False):
    if raw or "error" in res:
        print(json.dumps(res, indent=2, default=str))
        return
    print(res.get("answer", ""))
    for t in res.get("tools_used", []):
        print(f"  [tool] {t['tool']} {json.dumps(t['input'])}")
    for t in res.get("trace", []):
        print(f"  [trace] {json.dumps(t, default=str)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("mission")
    ap.add_argument("prompt")
    ap.add_argument("--conversation", help="stable conversation id (D3, D5)")
    ap.add_argument("--customer", help="signed-in customer id, e.g. C00112")
    ap.add_argument("--new-session", action="store_true")
    ap.add_argument("--raw", action="store_true")
    a = ap.parse_args()
    p = {"prompt": a.prompt}
    if a.conversation:
        p["conversation_id"] = a.conversation
    if a.customer:
        p["customer_id"] = a.customer
        p["actor_id"] = a.customer
    show(invoke(a.mission, p, a.new_session), a.raw)
