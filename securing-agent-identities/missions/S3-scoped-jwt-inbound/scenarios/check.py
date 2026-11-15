"""S3 check: the advisor agent accepts only workforce-pool tokens from the Advisor Portal carrying larchmont/advisor.invoke."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "common"))
sys.path.insert(0, HERE)
from callers import call, callers  # noqa: E402
from sai import check, finish, invoke_sigv4, session  # noqa: E402

o, cs = callers()
for name, url, client, scope, allowed in cs:
    cl, st, body = call(o, url, client, scope)
    if cl is None:
        check(f"{name}: token issued by Cognito", False, body)
        continue
    if allowed:
        check(f"{name}: invocation succeeds", st == 200 and isinstance(body, dict), f"HTTP {st} {body}")
        check(f"{name}: the agent sees the verified caller", isinstance(body, dict) and body.get("caller", {}).get("principal") == client["id"],
              f"{body.get('caller') if isinstance(body, dict) else body}")
    else:
        check(f"{name}: rejected by the runtime authorizer", st in (401, 403), f"HTTP {st} {body if st != 200 else 'ACCEPTED'}")

ok, body = invoke_sigv4(session(), o["runtime_arn"], {"action": "whoami"})
check("SigV4 callers are rejected (this runtime is JWT-only)", not ok, "accepted" if ok else "")
finish()
