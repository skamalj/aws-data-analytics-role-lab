# Agentic AI Demonstrated: break-fix practice missions

Six **break-fix missions** on **Amazon Bedrock AgentCore**, for practising the skills behind the
*AWS Agentic AI Demonstrated* microcredential in **your own AWS account**. Each mission's Terraform deploys a
working-looking but **deliberately broken** environment. Your job is to diagnose it from the symptoms and fix it in Terraform.

| Part | Where |
|---|---|
| Broken environment (Terraform) | `missions/<Mn-…>/terraform/` |
| Handout: situation, symptoms, objectives, toolkit, hint ladder, red herrings | `missions/<Mn-…>/README.md` |
| **Solution, kept separate:** root causes, explanations, debrief answers | `solutions/<Mn-…>/README.md` |
| Reference fix as a patch | `solutions/<Mn-…>/fix.patch` (`patch -p1 < …`) |

Every mission uses the same agent, **Trail Desk**, the customer assistant of the fictional outdoor retailer
*Riverbend Outfitters*. It's a small plain-Python agent ([`common/agent/agent.py`](common/agent/agent.py)) deployed to
**AgentCore Runtime** by direct code upload, with no containers. It uses the Bedrock Converse API with tool use. Environment variables
switch on gateway tools, knowledge-base search, memory, a DynamoDB tool and guardrails, so the agent stays the same in every mission
and the faults are always in the **infrastructure and configuration**.

## Missions

| # | Mission | Symptom | You'll work with | Faults | Time |
|---|---|---|---|---|---|
| M1 | [The front door is locked](missions/M1-identity-front-door/README.md) | The web console can't talk to the agent | Cognito OAuth 2.0 client credentials, Runtime **JWT authorizer**, execution role, inference-profile IAM | 3 | 40 min |
| M2 | [The agent can't use its tools](missions/M2-gateway-tool-routing/README.md) | Stock works, orders fail, returns never attempted | **AgentCore Gateway**, MCP, Lambda targets, tool schemas, gateway role | 3 | 40 min |
| M3 | [The manuals are there, but the agent can't find them](missions/M3-knowledge-base-on-s3-vectors/README.md) | No answers from product manuals | **Bedrock Knowledge Bases**, **S3 Vectors**, ingestion jobs, `Retrieve` | 3 | 50–60 min |
| M4 | [Every chat starts from zero](missions/M4-agentcore-memory/README.md) | Customers are treated like strangers | **AgentCore Memory**, strategies, namespaces, `actorId`/`sessionId` | 3 | 35–45 min |
| M5 | [Lights out on the public internet](missions/M5-private-networking/README.md) | Timeouts after moving to a private VPC | Runtime **VPC mode**, **PrivateLink** interface endpoints, private DNS, SGs, gateway endpoints | 3 | 45 min |
| M6 | [Trail Desk is oversharing](missions/M6-guardrails/README.md) | Leaks product plans, codes and staff PII | **Bedrock Guardrails**: denied topics, words, PII, regex, input/output, versions | 4 | 40 min |

The missions are independent. Do them in any order, and deploy one at a time.

## Prerequisites

- An AWS account where you're an administrator. **Use a sandbox, not production.**
- A Region with AgentCore, S3 Vectors and the models below. The default is **us-west-2** (us-east-1 also works: pass
  `-var region=us-east-1`, and for M5 also `-var 'availability_zone_ids=["use1-az1","use1-az2"]'`).
- Bedrock access to **Amazon Nova Lite** (`us.amazon.nova-lite-v1:0`, used by every mission) and **Titan Text Embeddings V2** (M3).
  Check *Bedrock > Model access*. To use another model, pass `-var model_id=<inference profile id>`.
- Terraform ≥ 1.6, AWS CLI v2 (recent enough for `bedrock-agentcore` commands), Python 3.10+ with `pip`, `boto3` ≥ 1.40, and `zip`.
  **AWS CloudShell** has nearly all of this. Install Terraform there (see the HashiCorp docs), or run from your laptop.

## Running a mission

```bash
./scripts/deploy.sh M1                      # builds the agent package, then terraform init + apply
cat missions/M1-identity-front-door/README.md
python3 common/chat.py M1 "Hi!"             # reproduce the symptom
# ... investigate, edit missions/M1-*/terraform/*.tf (and lambdas/ in M2), re-run deploy.sh ...
./scripts/destroy.sh M1                     # always tear down when finished
```

`common/chat.py` reads each mission's `terraform output`, gets an OAuth token when the runtime uses a JWT
authorizer (M1), or uses your AWS credentials with `InvokeAgentRuntime` (M2–M6). It keeps a session id per mission
in `.session-Mn` (`--new-session` starts a new one) and prints the agent's answer, the tools it used and a short
**trace** (gateway tools, tool errors, memory namespaces, guardrail interventions). `--raw` prints the full JSON.

Stuck? Climb the hint ladder in the handout first. To see the answer: `solutions/<mission>/README.md`.
To restore the broken state after applying a patch: `patch -R -p1 < solutions/<mission>/fix.patch`.

## Cost

Everything is pay-per-use and designed to stay small. There are no NAT gateways, no OpenSearch clusters, and no always-on compute.

| Item | Notes |
|---|---|
| AgentCore Runtime, Gateway, Memory | Billed by consumption (active CPU/memory seconds, requests, events and records). Pennies for a mission |
| Bedrock Nova Lite / Titan Embeddings | A few cents for a mission's worth of chats and one sync of five documents |
| Guardrails (M6) | Per 1,000 text units evaluated. Cents |
| S3 Vectors (M3) | Storage and queries for a few dozen vectors. Effectively zero |
| **Interface VPC endpoint (M5)** | ≈ $0.01 per hour per AZ (2 AZs), so **≈ $0.50/day while deployed**. The main reason to destroy promptly |
| Cognito (M1), Lambda (M2), DynamoDB (M5) | Free tier / negligible |

Run `./scripts/destroy.sh <mission>` as soon as you've finished. Budgets with an alert are a good idea.

## Layout

```
common/agent/agent.py             the Trail Desk agent (AgentCore Runtime HTTP contract: POST /invocations, GET /ping)
common/build_agent.sh             packages agent.py + boto3 for arm64 (direct code deployment)
common/chat.py                    client: OAuth (Cognito) or SigV4 invocation, session handling, trace output
common/terraform/agent_base/      code bucket + runtime execution role with baseline permissions
scripts/deploy.sh, destroy.sh
missions/Mn-*/                    handout + broken Terraform (+ lambdas/ or docs/ where needed)
solutions/Mn-*/                   explanation + fix.patch
```

These missions are original practice material written for self-study on the same skill areas. They aren't
affiliated with AWS or with any official assessment, and they don't reproduce exam content.
