# Databases for Agentic AI: break-fix missions

Five **break-fix missions** for practising the skills behind the *AWS Databases for Agentic AI Demonstrated*
microcredential in **your own AWS account**. The design follows the reference architecture in the published study guide:
an AI assistant for an online retailer whose data responsibilities are **separated**. It has structured queries, semantic retrieval,
persistent state and developer diagnostics, each with its own identity and controls.

Each mission deploys a deliberately broken environment with Terraform. You diagnose it from the symptoms and fix it.

| Part | Where |
|---|---|
| Handout: situation, symptoms, objectives, toolkit, hint ladder, red herrings | `missions/<Dn-…>/README.md` |
| Broken environment | `missions/<Dn-…>/terraform/` plus the code or SQL the mission is about |
| Self-checks | `missions/<Dn-…>/scenarios/*.py` |
| **Solution, kept separate**, with debrief answers | `solutions/<Dn-…>/README.md` |
| Reference fix | `solutions/<Dn-…>/fix.patch` (`patch -p1 < …`, undo with `patch -R -p1 < …`) |

## Missions

| # | Mission | Guide topic | You'll work with | Faults |
|---|---|---|---|---|
| D1 | [The agent sees nothing, or everything](missions/D1-structured-data/README.md) | Structured data (relational) | Aurora PostgreSQL, curated views, least-privilege DB identity, Secrets Manager, RDS Data API, Gateway Lambda tools, SQL injection | 3 |
| D2 | [Manuals in, nothing out](missions/D2-semantic-retrieval-pgvector/README.md) | Semantic retrieval (RAG) | Bedrock Knowledge Base on **Aurora pgvector**, vector dimensions, field mapping, HNSW/GIN indexes, KB identity | 3 |
| D3 | [Resume fails, and then the state explodes](missions/D3-persistent-agent-state/README.md) | Persistent agent state | **LangGraph** + **[`langgraph-dynamodb-checkpoint`](https://pypi.org/project/langgraph-dynamodb-checkpoint/)**, key schema, `thread_id`, TTL, 400 KB item limit, **[`agentstate-reducer`](https://pypi.org/project/agentstate-reducer/)** | 5 |
| D4 | [The debug tool is a backdoor](missions/D4-mcp-diagnostics/README.md) | Developer diagnostics (MCP) | **MCP server on AgentCore Runtime**, tool schemas, read-only identities (DB + IAM), limits, redaction | 3 |
| D5 | [Every question goes to the wrong place](missions/D5-orchestration-capstone/README.md) | Orchestration and routing | One LangGraph agent with all three capabilities, tool descriptions, injected caller context, data and state scoping | 3 |

Security, reliability and cost topics from the guide (secrets, encryption, timeouts, result limits, untrusted tool output,
capacity) are built into each mission.

## Architecture

```
                         ┌──────────── AgentCore Runtime: Trail Desk (plain Python or LangGraph) ────────────┐
 customer ─► web app ──► │  routing (tool descriptions + trusted request context: customer_id, conversation)   │
                         └───┬───────────────────────────┬───────────────────────────────┬────────────────────┘
                             │ MCP / SigV4               │ Retrieve                      │ checkpoints
                   AgentCore Gateway              Bedrock Knowledge Base           DynamoDB (langgraph-dynamodb-checkpoint)
                             │                           │ Data API as bedrock_kb_user
                   Lambda SQL tools ─Data API as trail_desk_app─► Aurora PostgreSQL Serverless v2 (shared "base" stack)
                                                         │          schemas: commerce (raw, PII) · reporting (curated views) · bedrock_kb (pgvector)
 engineer ─► coding agent ─MCP─► AgentCore Runtime: diagnostics MCP server ─Data API as diag_readonly─┘ + DynamoDB (read-only)
```

## Prerequisites

- A sandbox AWS account where you're an administrator. The default Region is **us-west-2** (pass `-var region=…` to every stack to change it).
- Bedrock access to **Amazon Nova Lite** (`us.amazon.nova-lite-v1:0`) and **Titan Text Embeddings V2**.
- Terraform ≥ 1.6, AWS CLI v2, Python 3.10+ with `pip`, `boto3` ≥ 1.40, and `zip`.

## Running

```bash
./scripts/deploy.sh base        # once: Aurora Serverless v2 + schema, 5,000 orders, DB identities (~10 min)
./scripts/deploy.sh D1          # any mission; D3 doesn't need base
cat missions/D1-structured-data/README.md
./scripts/destroy.sh D1
./scripts/destroy.sh base       # when you've finished all database missions
```

`deploy.sh` packages the agent for AgentCore Runtime (ARM64, direct code upload; the LangGraph missions are about 30 MB),
runs the mission's database `setup.py` if it has one, and applies the Terraform. Useful helpers:

```bash
python3 common/chat.py D1 "Where is order O1003?"                          # talk to a mission's agent
python3 common/chat.py D3 "..." --conversation c1 --customer C00042 --new-session
python3 common/dbsql.py --sql "SELECT * FROM reporting.category_activity"   # SQL as admin (or --as app|kb|diag)
```

## Cost

| Item | Notes |
|---|---|
| **Aurora Serverless v2 (base)** | Auto-pauses to **0 ACU** after 15 idle minutes (`min_acu = 0`), so you pay mostly for storage while idle. While active, ≈ 0.5–1 ACU ≈ $0.06–0.12 per hour. The first query after a pause takes ~15–30 s. Destroy `base` when you've finished |
| AgentCore Runtime / Gateway, Lambda, DynamoDB on-demand | Consumption-based. Pennies per mission |
| Bedrock (Nova Lite, Titan V2), Knowledge Base syncs | Cents |
| Secrets Manager | 3 secrets ≈ $0.40/month each while they exist |

## Third-party packages

D3 and D5 use `langgraph`, `langchain-core`, `langgraph-dynamodb-checkpoint` (0.5.0, with the `[reducer]` extra) and `agentstate-reducer`.
Their behaviour described in D3 (start-up table check, `PK`/`SK` schema, `ttl` attribute, reducer pruning) was verified against
`langgraph-dynamodb-checkpoint` 0.5.0's source. Pin the version if you reuse the missions.

These missions are original practice material for self-study. They aren't affiliated with AWS or with any official assessment.
