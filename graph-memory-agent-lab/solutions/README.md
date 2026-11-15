# Solutions

Open this only after you've tried the notebooks. Run every command from the project root, in the lab's virtual environment, with `.env`
created (`python scripts/make_env.py`). `src/config.py` loads `.env` itself. In a plain shell you can also export it with
`set -a; source .env; set +a`, which the `aws s3 cp` commands below need for `$EVIDENCE_BUCKET`.

`python solutions/apply_solution.py <goal…>` applies the code fixes below exactly. Undo them with `git checkout -- src/`.

**A fix isn't finished until its evidence is uploaded.** Grading reads the files in `s3://$EVIDENCE_BUCKET/evidence/`, not your
environment. Do the goals in order, because goal 4's evidence depends on the data seeded in goal 3.

## 1. Memory tools and turn order

**Goal:** register the missing memory tools on the governed MCP server, and correct the session read so the assistant stores and
recalls prior turns in chronological order.

- In `src/memory_client.py`, inside `get_session`, change `ScanIndexForward=False` to **`ScanIndexForward=True`** so turns come
  back oldest first.
  - This also fixes `append_turn`, which takes `existing[-1]` as the latest turn. In descending order that's turn 1, so it
    overwrote turn 2.
- In `src/mcp_server.py`, replace the `# TODO(DIY-1)` line with the two tools:

```python
@mcp.tool()
def append_turn(session_id: str, role: str, content: str) -> str:
    """Append one conversational turn to a session; returns the new turn_id."""
    turn_id = memory.append_turn(session_id, role, content)
    return json.dumps({"session_id": session_id, "turn_id": turn_id})


@mcp.tool()
def get_session(session_id: str) -> str:
    """Return all turns for a session, oldest first."""
    return json.dumps(memory.get_session(session_id), indent=2)
```

Publish:

```bash
python -m src.emit_evidence mcp-tools
aws s3 cp mcp_tools_result.json s3://$EVIDENCE_BUCKET/evidence/mcp_tools_result.json
```

**Don't append test turns to the `s-demo` session**, or the expected order `[1, 2, 3]` no longer matches. Notebook 01 has a reset cell.

## 2. IAM ownership boundary

**Goal:** close the over-broad IAM policy so the vector agent can no longer read another agent's private session memory.

1. In the IAM console, open the role whose name contains **`McpVectorRole`** (`gmlab-McpVectorRole` by default).
2. Delete the inline policy **`vector-memory-leak`**. It's the one whose statement `VectorStoreAccess` allows `dynamodb:GetItem` and
   `dynamodb:Query` on the `claims-sessions` table.
3. **Delete the whole policy; don't edit it.** Leave the role's other policy (`vector-store-access`: OpenSearch access plus the lab's
   deny rules) untouched.

CLI equivalent: `aws iam delete-role-policy --role-name gmlab-McpVectorRole --policy-name vector-memory-leak`, or
`python solutions/apply_solution.py 2 --yes`.

**Verify** with *Simulate* on the role. DynamoDB `GetItem` against the `claims-sessions` table ARN must be **denied**. Notebook 02 runs the
simulator and a live read as the role. No evidence upload is needed.

A later `terraform apply` in `infra/terraform` re-creates the policy. That's how you reset this goal.

## 3. Knowledge graph ontology

**Goal:** repair the broken commercial-property entity link, and author a new marine-cargo branch with its policy class and governed
loss-ratio metric, so both lines traverse from entity to the right metric. All edits are in `seed()` in `src/main.py`.

- **Repair the link.** Add a `class_uri` to the Nexus Tower entity:

```python
"class_uri": "urn:coa:ontology:CommercialPropertyPolicy",
```

- **Add the new class** (after `CommercialPropertyPolicy`, and before the metrics: `ingest_governed_metric` only links to classes that exist):

```python
ingest_ontology_class(
    lab,
    uri="urn:coa:ontology:MarineCargoPolicy",
    name="MarineCargoPolicy",
    description="Insurance policies covering goods in transit by sea and related cargo liabilities.",
    parent_uri="urn:coa:ontology:FinancialAsset",
)
```

- **Add the new governed metric:**

```python
ingest_governed_metric(
    lab,
    name="cargo_loss_ratio",
    description="Loss ratio for marine cargo lines: incurred losses divided by earned premium.",
    calculation_template="SELECT incurred_losses / earned_premium AS ratio FROM cargo_experience WHERE line_of_business = :lob",
    target_class_uris=["urn:coa:ontology:MarineCargoPolicy"],
    properties_used=["incurred_losses", "earned_premium", "line_of_business"],
)
```

- **Add the new entity** through a second document chunk:

```python
dual_ingest_document_chunk(
    lab,
    os_store,
    chunk_id="doc_chunk_102",
    text="Underwriting update for Atlantic Freight: Marine cargo policy underwritten for transatlantic container shipments with piracy and war risk exclusions.",
    source_uri="doc://underwriting/atlantic-freight-2026",
    extracted_entities=[
        {
            "id": "ent_atlantic_freight",
            "name": "Atlantic Freight",
            "type": "MarineCargo",
            "confidence": 0.97,
            "class_uri": "urn:coa:ontology:MarineCargoPolicy",
        }
    ],
    pg_store=pg_store,
)
```

- Change `wait_until_searchable(expected_count=1)` to **`expected_count=2`**.

Re-seed with the seed-only path, because a full run fails on the retrieval test until goal 4 is fixed. Then publish:

```bash
python -m src.main --seed-only
python -m src.emit_evidence ontology
aws s3 cp ontology_result.json s3://$EVIDENCE_BUCKET/evidence/ontology_result.json
```

The names `ent_atlantic_freight`, `MarineCargoPolicy` and `cargo_loss_ratio` must be exact. The evidence query, `metric_service.py` and
`assistant.py` look them up by name.

## 4. Hybrid retrieval

**Goal:** restore Reciprocal Rank Fusion so both vector stores return ranked hits with a fused score.

The error surfaces in `retriever.py` (`KeyError: 'score'`), but the score is never created in `src/opensearch_client.py`. Replace
`hybrid_vector_search` there:

```python
def hybrid_vector_search(self, query_text, query_vector, top_k: int = 3, rrf_k: int = 60):
    """Hybrid search: BM25 and kNN run separately, fused with Reciprocal Rank Fusion."""
    pool = max(top_k * 4, 10)
    fused = {}
    for hits in (self._bm25(query_text, pool), self._knn(query_vector, pool)):
        seen = set()
        rank = 0
        for doc in hits:
            cid = doc["chunk_id"]
            if cid in seen:
                continue
            seen.add(cid)
            rank += 1
            entry = fused.setdefault(cid, {**doc, "score": 0.0})
            entry["score"] += 1.0 / (rrf_k + rank)
    ranked = sorted(fused.values(), key=lambda d: d["score"], reverse=True)
    return ranked[:top_k]
```

- **Scoring.** Each result list contributes `1 / (60 + rank)` per document, so a chunk found by both keyword and vector search scores
  highest. The maximum is 2/61 ≈ 0.0328.
- **Why the `seen` set.** OpenSearch Serverless ignores client document ids, so each re-seed adds another copy of a chunk.

Publish the retrieval evidence and the benchmark:

```bash
python -m src.emit_evidence retrieval
aws s3 cp retrieval_result.json s3://$EVIDENCE_BUCKET/evidence/retrieval_result.json

python -m src.benchmark
aws s3 cp comparison_results.json s3://$EVIDENCE_BUCKET/evidence/comparison_results.json
```

## 5. Graph query guard

**Goal:** harden the graph read tool with an application-level guard that admits genuine read queries and rejects administrative,
procedure and write clauses.

In `src/mcp_server.py`, inside `execute_read_cypher`, replace the TODO comment block with:

```python
    normalized = " ".join(cypher_query.split()).upper()
    if not normalized.startswith(("MATCH", "OPTIONAL MATCH", "WITH", "UNWIND", "RETURN")):
        return "Rejected: only read queries (MATCH ... RETURN) are allowed."
    if "RETURN" not in normalized:
        return "Rejected: a read query must RETURN a result."
    for token in _FORBIDDEN_CYPHER:
        if token in normalized:
            return f"Rejected: disallowed clause '{token.strip()}'."
```

Publish:

```bash
python -m src.emit_evidence cypher-guard
aws s3 cp cypher_guard_result.json s3://$EVIDENCE_BUCKET/evidence/cypher_guard_result.json
```

## Check everything

```bash
python scripts/check_evidence.py
```

This reads your uploaded evidence the way the grader does, and checks goal 2 directly in IAM.
