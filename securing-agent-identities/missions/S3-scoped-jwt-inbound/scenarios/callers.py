"""
The callers of the portfolio advisor agent. Shows each caller's token claims and what the runtime answers.

    python3 missions/S3-scoped-jwt-inbound/scenarios/callers.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "common"))
from sai import base, claims, invoke_jwt, invoke_sigv4, mission, session, token  # noqa: E402


def callers():
    b, o = base(), mission(os.path.join(HERE, ".."))
    c = o["clients"]
    sp = b["scope_prefix"]
    return o, [
        ("advisor portal, scope advisor.invoke", b["token_url"], c["advisor_portal"], f"{sp}/advisor.invoke", True),
        ("advisor portal, scope reports.read only", b["token_url"], c["advisor_portal"], f"{sp}/reports.read", False),
        ("analytics dashboard, scope reports.read", b["token_url"], c["analytics"], f"{sp}/reports.read", False),
        ("staging portal (other user pool), advisor.invoke", o["staging_token_url"], c["staging"], "larchmont/advisor.invoke", False),
    ]


def call(o, url, client, scope):
    tok, err = token(url, client["id"], client["secret"], scope)
    if not tok:
        return None, None, f"token request failed: {err}"
    st, body = invoke_jwt(o["runtime_arn"], tok, {"action": "whoami"})
    return claims(tok), st, body


if __name__ == "__main__":
    o, cs = callers()
    for name, url, client, scope, _ in cs:
        cl, st, body = call(o, url, client, scope)
        print(f"== {name}")
        if cl:
            print("   claims:", json.dumps({k: cl.get(k) for k in ("iss", "client_id", "scope", "aud", "token_use")}))
        print(f"   runtime: HTTP {st} {json.dumps(body) if isinstance(body, dict) else body}")
    ok, body = invoke_sigv4(session(), o["runtime_arn"], {"action": "whoami"})
    print(f"== SigV4 (your IAM credentials)\n   runtime: {'OK ' + json.dumps(body) if ok else body}")
