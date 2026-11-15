# Mission D6 solution: pgvector finds nothing, then finds it slowly

```bash
patch -p1 < solutions/D6-pgvector-document-retrieval/fix.patch
./scripts/deploy.sh D6                                       # re-applies schema.sql (grant + index)
python3 missions/D6-pgvector-document-retrieval/ingest.py
python3 missions/D6-pgvector-document-retrieval/scenarios/check.py
```

## Fault 1: the ingestion job embeds with the wrong dimensions

| | |
|---|---|
| Symptom | `ingest.py` fails on the first chunk: `ERROR: expected 1024 dimensions, not 512` |
| Where | `ingest.py`: `EMBED_DIMENSIONS = 512` |
| Root cause | Titan V2 produces 256, 512 or 1024 dimensions on request. The column is `vector(1024)`, and the tool embeds queries at 1024. All three must agree, because vectors of different lengths can't even be compared |
| Fix | `EMBED_DIMENSIONS = 1024`. Moving to 512 would be legitimate (Mission D11), but only if the column type, the index, the query embeddings and every stored vector change together |

## Fault 2: the agent identity can see the schema but not read the table

| | |
|---|---|
| Symptom | `search_docs`: `permission denied for table doc_chunks` |
| Fix | `GRANT SELECT ON knowledge.doc_chunks TO trail_desk_app`. Grant `SELECT` only, because the agent must not be able to change its own knowledge (that's also a prompt-injection defence) |

## Fault 3: the HNSW index can't serve cosine queries

| | |
|---|---|
| Symptom | Results are correct but every query is a sequential scan (`Sort` → `Seq Scan`). It's fast at 50 rows and unusable at 5 million |
| Root cause | The index was built with `vector_l2_ops`, while the query orders by `<=>` (cosine). PostgreSQL can only use an index whose operator class matches the `ORDER BY` operator |
| Fix | `USING hnsw (embedding vector_cosine_ops)`. With it, the plan shows `Index Scan using doc_chunks_embedding_idx … Order By: (embedding <=> $0)` |

## Debrief answers

1. The column type (`vector(512)`) together with its index, the query-side `dimensions`, and a re-embedding of every stored row.
2. Ranking is the same, but the planner matches **operators**, not maths. `<->`, `<#>` and `<=>` are different operators, so pick one and build the index for it.
   Cosine is the safe default for Titan, because it doesn't depend on normalisation.
3. `m` (links per node) and `ef_construction` (candidate list at build time) trade build time and memory for recall. `ef_search` (candidate list at query time) trades
   query latency for recall, and also caps how many rows one index scan can return.
4. Least privilege. The pipeline needs `INSERT`/`UPDATE`, the agent only `SELECT`. If the agent's identity could write, a prompt-injected tool call
   could poison the knowledge base for every customer.
