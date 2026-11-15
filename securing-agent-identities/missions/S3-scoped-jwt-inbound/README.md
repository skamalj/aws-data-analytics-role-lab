# Challenge S3: The advisor agent's front door

**Exam objective:** *Configure scoped JWT authorization for inbound agent access*
**Services:** Amazon Bedrock AgentCore Runtime (inbound custom JWT authorizer), Amazon Cognito (user pools, resource servers, OAuth scopes, app clients)
**Time:** 25–35 minutes  |  **Deploy:** `./scripts/deploy.sh S3`

## Situation

The portfolio advisor agent (`larchmont_s3_portfolio_advisor`) runs on AgentCore Runtime with a custom JWT authorizer. Its inbound policy
is:

- Tokens must be issued by the **production workforce pool** (`larchmont-workforce`). The staging pool must never be trusted.
- Only the **Advisor Portal** app client may call it.
- The token must carry the scope **`larchmont/advisor.invoke`**. The Advisor Portal can also request `larchmont/reports.read` for its
  report widgets, and a token holding only that scope must **not** open the agent.
- SigV4/IAM callers aren't part of this path.

Users report that the portal is locked out. Security also flagged that the analytics dashboard was listed as an allowed caller during
testing.

Everything is in [`terraform/main.tf`](terraform/main.tf).

## Explore and check

```bash
python3 missions/S3-scoped-jwt-inbound/scenarios/callers.py     # each caller's token claims (iss, client_id, scope, aud) and the runtime's answer
python3 missions/S3-scoped-jwt-inbound/scenarios/check.py
aws bedrock-agentcore-control get-agent-runtime --agent-runtime-id <id> --query authorizerConfiguration
```

## Done when

`check.py` reports 6/6:
- the Advisor Portal with `advisor.invoke` gets through, and the agent sees the verified `client_id`;
- every other caller is rejected by the runtime before the agent runs.

<details><summary>Hint 1</summary>The authorizer fetches signing keys and the expected <code>iss</code> from the discovery URL. Compare the discovery URL with the <code>iss</code> claim in the portal's token.</details>
<details><summary>Hint 2</summary>Decode a Cognito <b>access</b> token. Which of the claims the authorizer can check (<code>aud</code>, <code>client_id</code>, <code>scope</code>) are actually present?</details>
<details><summary>Hint 3</summary>An allowed client restricts <i>who</i> is calling, and an allowed scope restricts <i>what the token was issued for</i>. The requirement needs both.</details>
