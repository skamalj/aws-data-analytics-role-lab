# Databases for Agentic AI: break-fix missions

Fourteen **break-fix missions** (plus a timed mock exam) for practising the skills behind the *AWS Databases for Agentic AI Demonstrated*
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

### Exam objectives → missions

The official exam lab (140 minutes) has seven objectives. Each one has at least one mission:

| Exam objective | Mission(s) |
|---|---|
| Configure Amazon Aurora PostgreSQL for agent access | **D1** |
| Configure pgvector for document retrieval | **D6** (also D9, D10, D11) |
| Configure Amazon DynamoDB for agent memory | **D3** |
| Implement Amazon Bedrock Knowledge Bases with Aurora | **D2** (Parts A + B), **D13** |
| Configure the Aurora MCP server for agent debugging | **D4** (Part A: custom MCP server on AgentCore; Part B: the AWS Labs PostgreSQL MCP server) |
| Configure the DynamoDB MCP server for state inspection | **D7** |
| Optimize the agent's product search queries | **D8** (CloudWatch SLA) |

### All missions

| # | Mission | Topic / source | You'll work with | Faults |
|---|---|---|---|---|
| D1 | [The agent sees nothing, or everything](missions/D1-structured-data/README.md) | Structured data | Aurora PostgreSQL, curated views, least-privilege DB identity, Secrets Manager, Data API, Gateway Lambda tools, SQL injection | 3 |
| D2 | [Manuals in, nothing out](missions/D2-semantic-retrieval-pgvector/README.md) | KB on Aurora + SimuLearn "Trustworthy LLMs" | Bedrock KB on **pgvector**, dimensions, field mapping, KB identity. **Part B:** metadata sidecars, allow-list audience filter | 3 + 2 |
| D3 | [Resume fails, and then the state explodes](missions/D3-persistent-agent-state/README.md) | Agent memory | **LangGraph** + **[`langgraph-dynamodb-checkpoint`](https://pypi.org/project/langgraph-dynamodb-checkpoint/)**, key schema, `thread_id`, TTL, 400 KB limit, **[`agentstate-reducer`](https://pypi.org/project/agentstate-reducer/)** | 5 |
| D4 | [The debug tool is a backdoor](missions/D4-mcp-diagnostics/README.md) | Aurora MCP server | MCP server on AgentCore Runtime, read-only identities, limits, redaction. **Part B:** `awslabs.postgres-mcp-server` flags | 3 + 4 |
| D5 | [Every question goes to the wrong place](missions/D5-orchestration-capstone/README.md) | Orchestration capstone | One LangGraph agent with all capabilities, tool descriptions, injected caller context, data and state scope | 3 |
| D6 | [pgvector finds nothing, then finds it slowly](missions/D6-pgvector-document-retrieval/README.md) | pgvector retrieval | Agent-side vector search, embedding dimensions, operator classes vs distance operators, read-only grants | 3 |
| D7 | [The memory inspector shows an empty brain](missions/D7-dynamodb-mcp-state-inspection/README.md) | DynamoDB MCP server | MCP server reading checkpoints **through `DynamoDBSaver`**, create-if-missing trap, read-only IAM, bounded/redacted output | 3 |
| D8 | [Product search is too slow for a conversation](missions/D8-product-search-optimization/README.md) | Query optimisation | 200k products, `EXPLAIN`, `pg_trgm`, composite and HNSW indexes, push-down, Data API 1 MB limit, **CloudWatch** EMF + dashboard | 3 |
| D9 | [Uploaded, but never searchable](missions/D9-diy-ingestion-pipeline/README.md) | aws-samples *rag-with-amazon-postgresql-using-pgvector* | S3 → EventBridge → Lambda chunk/embed → pgvector, model input limits, idempotent re-ingestion with transactions | 3 |
| D10 | [Fast answers, wrong answers](missions/D10-vector-index-recall/README.md) | Blog: *pgvector + Aurora for NLP/chatbots* | IVFFlat vs HNSW, `lists`/`probes`/`ef_search`, recall measured against exact search | 3 |
| D11 | [Fast RAG that isn't fast](missions/D11-high-speed-rag/README.md) | *Guidance for High-Speed RAG Chatbots* | 512-d embeddings done consistently, DynamoDB embedding cache, warm-start client reuse, latency budget | 3 |
| D12 | [Tenants see each other](missions/D12-multi-tenant-rls/README.md) | Blog: *Self-managed multi-tenant vector search* | Row-level security, owner bypass / `FORCE`, Data API sessions and transactions, filtered HNSW | 3 |
| D13 | [Partner A gets partner B's answers](missions/D13-multi-tenant-kb-metadata/README.md) | Blog: *Multi-tenant vector search with Bedrock KB* + SimuLearn | KB metadata sidecars (naming, format), `Retrieve` filters, tenant from trusted context | 3 |
| D14 | [How do customers feel about this product?](missions/D14-aurora-ml-sentiment/README.md) | Blog: *pgvector + Aurora … sentiment analysis* | **Aurora machine learning** (`aws_ml`) → Amazon Comprehend, role association per feature, materialising ML results | 3 |

Security, reliability and cost topics from the guide (secrets, encryption, timeouts, result limits, untrusted tool output, capacity) run through every mission.

### Mock exam

```bash
./scripts/exam.sh start            # deploys base + the 7 objective challenges (D1 D2 D3 D4 D6 D7 D8), shuffles them, starts a 140-minute clock
cat exam/briefing.md               # situation + objectives per challenge - no hints
./scripts/exam.sh status           # time left
./scripts/exam.sh grade            # runs every challenge's scenarios/check.py and prints a score
./scripts/exam.sh end              # destroys the challenge stacks (then ./scripts/destroy.sh base)
```

`./scripts/exam.sh start all` includes every mission, and `./scripts/exam.sh start D6,D8,D12` picks your own set.
Every mission has `scenarios/check.py` as its grading entry point.

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
./scripts/deploy.sh D1          # any mission; D3 and D7 don't need base
python3 missions/D1-structured-data/scenarios/check.py   # every mission: PASS/FAIL self-check
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
| Secrets Manager | 3 secrets (+1 in D12) ≈ $0.40/month each while they exist |
| Amazon Comprehend (D14) | 600 reviews scored once: cents |
| D8 / D10 / D12 data | Generated inside Aurora with SQL (200k products, 20k and 30k vectors): no embedding cost |

## Third-party packages

D3 and D5 use `langgraph`, `langchain-core`, `langgraph-dynamodb-checkpoint` (0.5.0, with the `[reducer]` extra) and `agentstate-reducer`.
Their behaviour described in D3 (start-up table check, `PK`/`SK` schema, `ttl` attribute, reducer pruning) was verified against
`langgraph-dynamodb-checkpoint` 0.5.0's source. Pin the version if you reuse the missions.

## What has (and hasn't) been tested

Nothing in this kit has been deployed to AWS by its author. All Terraform passes `terraform validate` against the AWS provider (6.72),
all SQL (schemas, grants, row-level security, pgvector index and recall behaviour) was run on PostgreSQL 16 + pgvector 0.6, the Python
logic (checkpointer faults, MCP servers, Lambda tools) was tested locally with moto and stand-in models, and every solution patch applies.
Service-side behaviour (exact AWS error texts, AgentCore start-up, Aurora-only features such as `aws_ml` and pgvector 0.8, real latencies)
is untested, so expect small adjustments on the first real deployment of each mission.

These missions are original practice material for self-study. They aren't affiliated with AWS or with any official assessment.
