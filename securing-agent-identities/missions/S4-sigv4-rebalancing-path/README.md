# Challenge S4: The rebalancing service can't reach its agent

**Exam objective:** *Configure a SigV4 path for the rebalancing service*
**Services:** Amazon Bedrock AgentCore Runtime (IAM/SigV4 inbound, `runtimeUserId`), AgentCore Identity (user-scoped workload tokens, OAuth2 M2M via the token vault), AWS IAM
**Time:** 25–35 minutes  |  **Deploy:** `./scripts/deploy.sh S4`

## Situation

Every night, the internal **rebalancing service** (IAM role `larchmont-s4-rebalancing-service`) asks the rebalancer agent
(`larchmont_s4_rebalancer`) to prepare trades for each portfolio manager. It's a service, not a person, so it has no Cognito token. It
signs its calls with **SigV4** and passes the portfolio manager as **`runtimeUserId`**. The agent then fetches a Ledger API token from
the token vault (OAuth2 client credentials, scope `larchmont/ledger.read`) to read positions.

Requirements:
- The rebalancing service can invoke **this agent only**, and may act on behalf of a portfolio manager.
- The ops console (`larchmont-s4-ops-console`) may invoke the agent for health checks, but must **never** act on behalf of a user.
- The agent gets its Ledger token through the token vault. No credentials are configured on the agent.

The rebalancer was cloned from the advisor agent's template last week, and no rebalancing run has succeeded since.

Everything is in [`terraform/main.tf`](terraform/main.tf).

## Run and check

```bash
python3 missions/S4-sigv4-rebalancing-path/scenarios/rebalance.py                 # as the rebalancing service, for pm-0042
python3 missions/S4-sigv4-rebalancing-path/scenarios/rebalance.py --as ops --user ''
python3 missions/S4-sigv4-rebalancing-path/scenarios/check.py
```

The agent's logs are in CloudWatch Logs `/aws/bedrock-agentcore/runtimes/larchmont_s4_rebalancer-*`.

## Done when

`check.py` reports 7/7:
- the service's SigV4 call succeeds and the agent gets its Ledger token;
- the ops console works without user delegation and is denied with it;
- the service can't invoke other runtimes.

<details><summary>Hint 1</summary>One runtime has one inbound authorizer. What happens to a SigV4 request at a runtime configured for JWTs?</details>
<details><summary>Hint 2</summary>Compare the <code>Resource</code> in the service's policy, character by character, with the runtime's real ARN (<code>terraform output runtime_arn</code>).</details>
<details><summary>Hint 3</summary>Passing <code>runtimeUserId</code> is a privilege of its own. And API keys and OAuth tokens come out of the token vault through different actions.</details>
