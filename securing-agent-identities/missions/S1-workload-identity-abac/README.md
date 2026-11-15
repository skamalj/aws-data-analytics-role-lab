# Challenge S1: Any operator can act as any agent

**Exam objective:** *Restrict workload identity access by using tag-based access control*
**Services:** Amazon Bedrock AgentCore Identity (workload identities, workload access tokens), AWS IAM (ABAC: principal and resource tags, condition keys)
**Time:** 20–30 minutes  |  **Deploy:** `./scripts/deploy.sh S1` (after `./scripts/deploy.sh base`)

## Situation

Larchmont Wealth runs a fleet of agents, each with an AgentCore **workload identity**. Anyone who can call `GetWorkloadAccessToken` for a
workload identity can act as that agent towards the token vault. They can fetch its API keys and OAuth tokens.

The platform team decided on **attribute-based access control** so that one policy scales to every team and every new agent:

- every workload identity carries a `team` tag naming its owning team;
- every operator role carries a `team` tag;
- one shared IAM policy, `larchmont-s1-workload-token-access`, attached to every operator role, allows minting workload access tokens
  **only when the workload identity's team equals the operator's team**;
- ownership tags are the access policy, so **operators must not be able to change them**.

| Workload identity | Agent | Owning team (per the service catalogue) |
|---|---|---|
| `larchmont-s1-advisor-agent` | portfolio advisor | advisory |
| `larchmont-s1-rebalancer-agent` | rebalancer | trading |
| `larchmont-s1-reporting-agent` | regulatory reporting | compliance |

Operator roles: `larchmont-s1-advisory-ops`, `larchmont-s1-trading-ops` and `larchmont-s1-compliance-ops`.

Today nobody can mint a token at all, and the auditors' review of the tags and policy found more problems behind that.

Everything is in [`terraform/main.tf`](terraform/main.tf).

## Explore and check

```bash
python3 missions/S1-workload-identity-abac/scenarios/probe.py    # the operator x agent access matrix
python3 missions/S1-workload-identity-abac/scenarios/check.py    # PASS/FAIL
aws bedrock-agentcore-control list-tags-for-resource --resource-arn <workload identity ARN>
aws iam list-role-tags --role-name larchmont-s1-compliance-ops
```

## Done when

`check.py` reports 11/11:
- each team mints tokens for its own agent;
- each team is denied for the other two;
- trading operators can't re-tag the advisor's identity.

<details><summary>Hint 1</summary><code>aws:RequestTag</code>, <code>aws:ResourceTag</code> and <code>aws:PrincipalTag</code> describe three different things. Which one is "the tag on the workload identity being used"?</details>
<details><summary>Hint 2</summary>ABAC compares two tags. If either side is missing, the condition can't match. Check both the resources and the principals.</details>
<details><summary>Hint 3</summary>If I can change a resource's tags, I can grant myself access to it. Which statement lets operators do that?</details>
