"""
File a regulatory report the way each caller does.

    python3 missions/S5-reporting-agent-jwt-migration/scenarios/file_report.py --as compliance [--acting-as cfo]
    python3 missions/S5-reporting-agent-jwt-migration/scenarios/file_report.py --as legacy-batch --acting-as officer-17
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "common"))
from sai import base, invoke_jwt, invoke_sigv4, mission, session, token  # noqa: E402


def file(who, acting_as=None, report="Q3 suspicious-activity summary"):
    b, o = base(), mission(os.path.join(HERE, ".."))
    payload = {"action": "file_report", "report": report}
    if acting_as:
        payload["acting_as"] = acting_as
    if who == "legacy-batch":
        ok, body = invoke_sigv4(session(o["legacy_batch_role_arn"]), o["runtime_arn"], payload)
        return (200 if ok else 403), body
    if who == "forged":
        return invoke_jwt(o["runtime_arn"], "eyJhbGciOiJub25lIn0.eyJjbGllbnRfaWQiOiJjZm8ifQ.", payload)
    client = o["clients"]["compliance_portal" if who == "compliance" else "advisor_portal"]
    scope = f"{b['scope_prefix']}/" + ("reports.submit" if who == "compliance" else "advisor.invoke")
    tok, err = token(b["token_url"], client["id"], client["secret"], scope)
    if not tok:
        return None, f"token request failed: {err}"
    return invoke_jwt(o["runtime_arn"], tok, payload)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--as", dest="who", default="compliance", choices=["compliance", "advisor", "legacy-batch", "forged"])
    ap.add_argument("--acting-as", help="the (unverified) identity the caller claims in the payload")
    a = ap.parse_args()
    st, body = file(a.who, a.acting_as)
    print(f"status {st}\n" + (json.dumps(body, indent=2) if isinstance(body, dict) else str(body)))
