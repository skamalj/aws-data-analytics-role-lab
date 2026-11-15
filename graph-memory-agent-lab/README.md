# Graph Memory Agent lab: interactive notebooks, run from your laptop

An interactive version of the **claims knowledge-graph assistant** exercise. The assistant is an MCP server that combines:
- DynamoDB conversational memory;
- a Neo4j ontology with governed metrics;
- hybrid retrieval over OpenSearch and Aurora pgvector;
- Bedrock (Titan embeddings, Nova Pro).

The lab hands you that system with five gaps to close.

**Nothing runs on EC2.** The original lab's on-box code (`src/`) runs in **Jupyter notebooks on your laptop**, calling AWS with **your
credentials**. Neo4j runs locally. Everything else is a managed AWS service created by Terraform. No containers are required.

| Component | Where | Created by |
|---|---|---|
| `src/` (MCP server, seed, evidence, benchmark), notebooks | your laptop | this repo |
| Neo4j **5.13+** (graph + metric vector index) | your laptop | you (Neo4j Desktop or a package install) |
| DynamoDB `claims-sessions` (Agent A memory) | AWS | `infra/terraform` |
| IAM `gmlab-McpVectorRole`, **with the goal 2 leak** | AWS | `infra/terraform` |
| OpenSearch **Serverless** VECTORSEARCH collection (BM25 + kNN, faiss) | AWS | `infra/terraform` |
| **Aurora PostgreSQL** Serverless v2 **16.6** with **pgvector** (vector store B + metric source of record) | AWS (or a local PostgreSQL with pgvector) | `infra/terraform` |
| S3 evidence bucket | AWS | `infra/terraform` |
| Bedrock: Titan Text Embeddings V2, Amazon Nova Pro | AWS (model access) | you |

**pgvector on Aurora.** The lab creates `vector(1024)` columns with an **HNSW** index (`vector_cosine_ops`), which needs pgvector 0.5.0
or later.
- Aurora PostgreSQL 16.6 ships pgvector 0.8.0, and the lab's `CREATE EXTENSION vector` works as the master user.
- 16.6 also supports Serverless v2 **auto-pause** (`min_capacity = 0`), so an idle cluster costs only storage.
- For a local PostgreSQL instead, install pgvector 0.5+ and run Terraform with `-var create_aurora=false`.

## The five goals

| # | Goal | Notebook | Where you work | Evidence |
|---|---|---|---|---|
| 1 | Memory tools and turn order | [`01_memory_tools_and_turn_order`](notebooks/01_memory_tools_and_turn_order.ipynb) | `src/memory_client.py`, `src/mcp_server.py` | `mcp_tools_result.json` |
| 2 | IAM ownership boundary | [`02_iam_ownership_boundary`](notebooks/02_iam_ownership_boundary.ipynb) | IAM console (no code) | none (checked in IAM) |
| 3 | Knowledge graph ontology | [`03_knowledge_graph_ontology`](notebooks/03_knowledge_graph_ontology.ipynb) | `src/main.py` (`seed()`) | `ontology_result.json` |
| 4 | Hybrid retrieval (RRF) | [`04_hybrid_retrieval_rrf`](notebooks/04_hybrid_retrieval_rrf.ipynb) | `src/opensearch_client.py` | `retrieval_result.json`, `comparison_results.json` |
| 5 | Graph query guard | [`05_graph_query_guard`](notebooks/05_graph_query_guard.ipynb) | `src/mcp_server.py` (`execute_read_cypher`) | `cypher_guard_result.json` |

Start with [`00_setup_and_seed`](notebooks/00_setup_and_seed.ipynb) and finish with the bonus [`06_grounded_assistant`](notebooks/06_grounded_assistant.ipynb).
Do the goals **in order**: goal 4's evidence depends on the data seeded in goal 3.

### Technology walkthroughs (optional, ungraded)

Deep dives into the two vector engines agentic systems lean on. Each runs against the lab's own Aurora and OpenSearch, using 40
insurance clauses ([`notebooks/data/clauses.json`](notebooks/data/clauses.json)) embedded once with Titan and cached locally. Each works in
a **scratch schema or index** and cleans up after itself, so it never touches the graded data.

| Notebook | Covers | Most useful before |
|---|---|---|
| [`07_pgvector_walkthrough`](notebooks/07_pgvector_walkthrough.ipynb) | `vector` / `halfvec` / `sparsevec`; the `<->` `<=>` `<#>` operators and matching operator classes; `EXPLAIN`; HNSW (`ef_search`) vs IVFFlat (`probes`) **recall measured against exact search** on 20k vectors; filtered search and 0.8 **iterative scans**; **hybrid full-text + vector RRF in one SQL query**; agent memory tables; **row-level security** per tenant; Aurora notes | goals 3–4 |
| [`08_opensearch_walkthrough`](notebooks/08_opensearch_walkthrough.ipynb) | Serverless collections, the encryption/network/data-access policies and SigV4; `knn_vector` mapping (engine, space type, HNSW); eventual consistency and **upsert by business key** without document ids; **analyzers** (`english` vs `standard`); kNN scores vs BM25; **post-filter vs efficient filtered kNN**; client RRF vs **server-side hybrid pipelines**; an MCP retrieval tool with the **tenant taken from trusted context**; how Bedrock Knowledge Bases use it | goal 4 |

Each notebook follows the same pattern:
1. a short concept explainer;
2. cells that **reproduce the defect live**;
3. the task, with a hint ladder (you edit `src/*.py` in your editor; the notebook reloads it);
4. verification cells;
5. **publish the evidence**: run `emit_evidence` and upload to S3;
6. the local grader.

**Grading reads the evidence**, not your environment. A fix isn't finished until its evidence file is in
`s3://$EVIDENCE_BUCKET/evidence/`.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m ipykernel install --user --name gmlab

terraform -chdir=infra/terraform init
terraform -chdir=infra/terraform apply -var my_ip_cidr=$(curl -s https://checkip.amazonaws.com)/32   # ~10-15 min
python scripts/make_env.py            # writes .env (asks for your local Neo4j password)

jupyter lab notebooks/                # open 00_setup_and_seed, kernel "gmlab"
```

## Repository layout

| Path | What |
|---|---|
| `src/` | The lab's code **with the five gaps**, unchanged except for one laptop adaptation (below) |
| `notebooks/` | `00`–`06` (setup and goals), `07`–`08` (walkthroughs), `data/clauses.json`, and `labkit.py` (loads `.env`, reloads edited modules, uploads evidence, cached Titan embeddings, runs the grader) |
| `infra/terraform/` | DynamoDB, S3, IAM (with the leak), OpenSearch Serverless, Aurora + pgvector |
| `scripts/make_env.py` | Writes `.env` from the Terraform outputs plus your Neo4j settings |
| `scripts/check_evidence.py` | Local grader: reads your evidence from S3 and checks goal 2 in IAM |
| `tests/test_offline.py` | `pytest` self-checks per goal that need no AWS or databases (moto + fakes). They fail before a fix and pass after |
| `solutions/` | `README.md` (every fix and its publish commands) and `apply_solution.py` (applies the reference fixes) |

**Laptop adaptation in `src/`.** `pgvector_client.py` reads `PGSSLMODE` (default `require`, as before), so a local PostgreSQL without
TLS also works. Nothing else in `src/` was changed. `src/preflight.py` still mentions internal credential tooling in a hint. Ignore it
and use your normal AWS credentials.

## Running the commands outside the notebooks

Every notebook step is a plain command, run from the project root:

```bash
set -a; source .env; set +a              # optional: src/config.py loads .env itself
python -m src.preflight
python -m src.main --seed-only
python -m src.emit_evidence mcp-tools && aws s3 cp mcp_tools_result.json s3://$EVIDENCE_BUCKET/evidence/
python scripts/check_evidence.py
pytest tests -q -k goal1
```

## Cost and clean-up

| Item | Cost while it exists |
|---|---|
| **OpenSearch Serverless** | The main cost: a minimum of about 1 OCU (≈ $0.24 per hour) with standby replicas disabled, around $5.80 per day. **Destroy it when you're done** |
| Aurora Serverless v2 | Pauses to 0 ACU after 30 idle minutes, leaving storage only (cents). About $0.12 per ACU-hour while active |
| DynamoDB on-demand, S3, Bedrock | Cents for this lab |

```bash
terraform -chdir=infra/terraform destroy
```

Goal 2 is reset by `terraform apply`, which re-creates the leaky inline policy. Code goals are reset with `git checkout -- src/`.

## What has and hasn't been tested

This lab was written without running anything:
- no `terraform apply`, and no notebook executed against AWS, Neo4j or PostgreSQL;
- not even `terraform validate` or `pytest`.

The notebooks import and call the lab's own `src/` code, and the evidence they publish is produced by the lab's own `emit_evidence.py`
and `benchmark.py`. Expect small fixes on the first run. The most likely places are:
- the OpenSearch Serverless policies (the data access principal is derived from your current credentials);
- reaching the public Aurora endpoint from your network;
- `jupyter` and `mcp` package versions.
