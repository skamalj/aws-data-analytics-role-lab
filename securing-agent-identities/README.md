# Securing Agent Identities Demonstrated: break-fix challenges

Six **break-fix challenges**, plus a timed 135-minute mock exam, for practising the skills behind the *AWS Securing Agent Identities
Demonstrated* microcredential in **your own AWS account**.

The scenario is **Larchmont Wealth**, a fictional wealth manager running a fleet of Amazon Bedrock AgentCore agents:
- a portfolio advisor;
- a rebalancer driven by an internal service;
- a regulatory reporting agent;
- a self-hosted research agent on EC2.

Every challenge hardens one identity path: who may *be* an agent, who may *call* an agent, and who notices when someone tries.

| Part | Where |
|---|---|
| Handout: situation, requirements, how to reproduce, hint ladder | `missions/<Sn-…>/README.md` |
| Broken environment | `missions/<Sn-…>/terraform/` |
| Self-check (PASS/FAIL) | `missions/<Sn-…>/scenarios/check.py` |
| **Solution, kept separate** | `solutions/<Sn-…>/README.md` (each fault, why it happens, the fix) |
| Reference fix | `solutions/<Sn-…>/fix.patch` (`patch -p1 < …`, undo with `patch -R -p1 < …`) |

## Exam objectives → challenges

| Exam objective | Challenge | You'll work with | Faults |
|---|---|---|---|
| Restrict workload identity access by using tag-based access control | [**S1** Any operator can act as any agent](missions/S1-workload-identity-abac/README.md) | Workload identities, `GetWorkloadAccessToken`, IAM ABAC (`aws:ResourceTag` vs `aws:RequestTag` vs `aws:PrincipalTag`), tag tampering | 4 |
| Provision a workload identity for a self-hosted agent | [**S2** The research agent has no identity](missions/S2-self-hosted-workload-identity/README.md) | `CreateWorkloadIdentity`, an **EC2** agent managed by **Systems Manager** (Run Command, Parameter Store), token vault API keys, Secrets Manager | 4 |
| Configure scoped JWT authorization for inbound agent access | [**S3** The advisor agent's front door](missions/S3-scoped-jwt-inbound/README.md) | Runtime custom JWT authorizer: discovery URL, `allowed_clients`, `allowed_scopes`, why `allowed_audience` fails with **Cognito** access tokens | 4 |
| Configure a SigV4 path for the rebalancing service | [**S4** The rebalancing service can't reach its agent](missions/S4-sigv4-rebalancing-path/README.md) | IAM-authorized runtime, runtime ARNs, `runtimeUserId` + `InvokeAgentRuntimeForUser`, OAuth2 M2M through the token vault | 4 |
| Migrate the regulatory reporting agent to JWT-based identity verification | [**S5** Anyone can file as anyone](missions/S5-reporting-agent-jwt-migration/README.md) | IAM → JWT migration, `request_header_allowlist`, identity from verified claims instead of the payload, closing the legacy path | 4 |
| Detect identity security events by using AWS CloudTrail and Amazon CloudWatch | [**S6** Nobody noticed](missions/S6-identity-audit-detection/README.md) | Trail → CloudWatch Logs delivery, advanced event selectors (management vs data events), metric filters, alarms, SNS, incident drill | 5 |

All the services listed for the exam are covered:
- Amazon Bedrock (AgentCore Runtime and Identity)
- AWS CloudTrail
- Amazon CloudWatch
- Amazon Cognito
- Amazon EC2
- IAM
- Amazon S3
- Systems Manager

Secrets Manager and SNS also appear.

## Prerequisites

- A sandbox AWS account where you're an administrator, in a Region with AgentCore. The default is **us-west-2**: pass `-var region=…` to every stack to change it.
- Terraform ≥ 1.6, AWS CLI v2 (recent enough for `bedrock-agentcore`), Python 3.10+ with `boto3` ≥ 1.40, `pip` and `zip`.
- No model access is needed. The agent is a small plain-Python service ([`common/agent/agent.py`](common/agent/agent.py)) so the challenges
  stay about identity. It exposes three actions:
  - `whoami`: who is calling and with which identity;
  - `credential`: fetch an API key or OAuth token from the token vault;
  - `file_report`: record a filing under the caller's identity.

## Running

```bash
./scripts/deploy.sh base       # once: builds the agent package; Cognito pool + scopes, token-vault credential providers, code bucket
./scripts/deploy.sh S1         # any challenge
cat missions/S1-workload-identity-abac/README.md
python3 missions/S1-workload-identity-abac/scenarios/check.py
./scripts/destroy.sh S1
./scripts/destroy.sh base      # when you've finished
```

The base stack contains:
- Cognito user pool `larchmont-workforce` with resource server `larchmont` and scopes `advisor.invoke`, `reports.read`, `reports.submit` and `ledger.read`;
- an OAuth2 credential provider (`larchmont-ledger-api`, client credentials against the same pool), standing in for an internal Ledger API;
- an API key credential provider (`larchmont-market-data-api`, a dummy key) for a Market Data API.

### Mock exam

```bash
./scripts/exam.sh start            # deploys base + S1..S6, shuffles them, starts a 135-minute clock
cat exam/briefing.md               # each challenge's brief, hints removed
./scripts/exam.sh status
./scripts/exam.sh grade            # runs every challenge's scenarios/check.py and prints a score
./scripts/exam.sh end              # destroys the challenge stacks (then ./scripts/destroy.sh base)
```

S6's final checks need the incident drill after your fixes, plus ~15 minutes of CloudTrail delivery, so start S6 early.

## Cost

| Item | Notes |
|---|---|
| EC2 (S2) | One t3.micro, about $0.01 per hour. Destroy S2 when you're done |
| AgentCore Runtime (S3–S5) | Consumption-based. The agent does almost no work: cents |
| CloudTrail (S6) | The trail's management events are free (first copy). Data events are $0.10 per 100,000. CloudWatch Logs ingestion is cents |
| Cognito, AgentCore Identity, Secrets Manager | Cognito M2M tokens cost cents at this volume. The token vault stores two secrets (~$0.40/month each while base exists) |

## What has (and hasn't) been tested

Nothing in this kit has been deployed to AWS by its author.
- **Terraform:** all of it passes `terraform validate` against the AWS provider (6.72).
- **Patches:** every solution patch applies.
- **Agent:** exercised locally (HTTP contract, JWT/payload identity modes, self-hosted mode, token-vault calls against a stub).
- **Checks:** the S1, S3 and S5 checks were run against simulated AWS behaviour. Each fails on the broken configuration and passes on the
  fixed one. The S2, S4 and S6 checks have only been syntax-checked.
- **Untested service-side behaviour:**
  - whether workload-identity token calls honour `aws:ResourceTag` conditions (S1);
  - the exact IAM resources the token vault authorizes;
  - the header name the runtime uses to deliver the workload access token (`WorkloadAccessToken`, as in the AgentCore SDK);
  - whether `AWS::BedrockAgentCore::WorkloadIdentity` is accepted as a data-event type (S6);
  - exact AWS error texts.

  Expect small adjustments on the first real deployment of each challenge.

These challenges are original practice material for self-study. They aren't affiliated with AWS or with any official assessment.
