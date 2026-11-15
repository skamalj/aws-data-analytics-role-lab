"""S4 check: the rebalancing service reaches the rebalancer over SigV4 for a portfolio manager; nobody else gets more than they need."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "common"))
from sai import check, finish, invoke_sigv4, mission, session  # noqa: E402

o = mission(os.path.join(HERE, ".."))
svc = session(o["service_role_arn"])
ok, body = invoke_sigv4(svc, o["runtime_arn"], {"action": "credential"}, user_id="pm-0042")
check("the rebalancing service invokes the rebalancer with SigV4 on behalf of pm-0042", ok, "" if ok else body)
body = body if ok else {}
check("the agent received a workload access token", body.get("workload_token") is True, f"{body}" if ok else "")
check("the agent obtained a Ledger API token (OAuth2 M2M) from the token vault", body.get("credential") == "obtained",
      f"{body.get('error', '')} {body.get('message', '')}".strip())

ops = session(o["ops_console_role_arn"])
ok2, b2 = invoke_sigv4(ops, o["runtime_arn"], {"action": "whoami"})
check("the ops console can invoke without user delegation", ok2, "" if ok2 else b2)
ok3, b3 = invoke_sigv4(ops, o["runtime_arn"], {"action": "whoami"}, user_id="pm-0042")
check("the ops console cannot act on behalf of a user (InvokeAgentRuntimeForUser denied)", not ok3 and "AccessDenied" in b3, "accepted" if ok3 else b3)

iam = session().client("iam")
other = o["runtime_arn"].rsplit("/", 1)[0] + "/some_other_agent-AbCdEf1234"
r = iam.simulate_principal_policy(PolicySourceArn=o["service_role_arn"], ActionNames=["bedrock-agentcore:InvokeAgentRuntime"], ResourceArns=[other])
decision = r["EvaluationResults"][0]["EvalDecision"]
check("the rebalancing service cannot invoke any other agent runtime", decision != "allowed", f"simulated decision for {other}: {decision}")
finish()
