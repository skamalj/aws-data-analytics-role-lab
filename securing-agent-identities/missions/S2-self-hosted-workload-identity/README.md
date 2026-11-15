# Challenge S2: The research agent has no identity

**Exam objective:** *Provision a workload identity for a self-hosted agent*
**Services:** Amazon Bedrock AgentCore Identity (workload identities, token vault, API key credential providers), Amazon EC2, AWS Systems Manager (Run Command, Parameter Store), AWS IAM, AWS Secrets Manager
**Time:** 25–35 minutes  |  **Deploy:** `./scripts/deploy.sh S2` (one t3.micro instance)

## Situation

The research agent isn't on AgentCore Runtime. It runs on an EC2 instance (`larchmont-s2-research-agent-host`) because it needs a
licensed analytics library. Operations reach the host only through **Systems Manager**: it has no SSH key and no inbound ports. The agent:

1. reads its configuration from Parameter Store (`/larchmont/research-agent/workload-name` and `/credential-provider`);
2. calls **`GetWorkloadAccessToken`** with the instance role's credentials, to get a token that says "I am workload `larchmont-s2-research-agent`";
3. exchanges that token at the **token vault** (`GetResourceApiKey`) for the Market Data API key. The key isn't stored on the host.

Security requirements:
- The agent has its **own** workload identity, tagged `team = research` (the fleet's ABAC standard from S1).
- The host role gets only what the agent needs: no administrator access and no wildcard AgentCore permissions.
- The host is operable through Systems Manager only.

Ticket SEC-114 ("provision the research agent's workload identity") is still open, and the agent has never worked.

Everything is in [`terraform/main.tf`](terraform/main.tf). The agent's code is [`common/agent/agent.py`](../../common/agent/agent.py) (`self_hosted()`).

## Run and check

```bash
python3 missions/S2-self-hosted-workload-identity/scenarios/run_agent.py            # runs the agent on the host through SSM Run Command
python3 missions/S2-self-hosted-workload-identity/scenarios/check.py
aws ssm describe-instance-information
```

A newly launched (or newly permitted) host takes a few minutes to register with Systems Manager.

## Done when

`check.py` reports 7/7:
- the identity exists and is tagged;
- the host is managed and least-privilege;
- the agent gets a workload access token and the API key.

<details><summary>Hint 1</summary>AgentCore Runtime creates a workload identity for each runtime automatically. Who creates one for an agent that runs somewhere else?</details>
<details><summary>Hint 2</summary>Before Run Command can reach an instance, the SSM Agent on it has to authenticate. With which permissions?</details>
<details><summary>Hint 3</summary>There are three <code>GetWorkloadAccessToken*</code> APIs. Which one fits an agent acting for itself, with no user in the picture? And where does the token vault keep the API key it hands back?</details>
