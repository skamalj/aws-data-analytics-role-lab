# Mission D10 solution: Fast answers, wrong answers

```bash
patch -p1 < solutions/D10-vector-index-recall/fix.patch
./scripts/deploy.sh D10
python3 missions/D10-vector-index-recall/scenarios/check.py
```

Measured on PostgreSQL 16 with pgvector 0.6 and the same generator: IVFFlat recall@10 goes from **0.52 to 1.00**, and HNSW recall@100 from **0.36 (40 rows) to 0.999 (100 rows)**.

## Fault 1: IVFFlat built on an empty table, with far too many lists

| | |
|---|---|
| Root cause | `CREATE INDEX … ivfflat … WITH (lists = 1000)` ran **before** `INSERT`. IVFFlat clusters the rows that exist at build time, so with no data the centroids are arbitrary and rows are filed into the wrong lists. pgvector even warns *"ivfflat index created with little data … This will cause low recall."* 1,000 lists for 20,000 rows also leaves ~20 rows per list |
| Fix | Load first, then build. `lists ≈ rows / 1000` (or about √rows for small tables), here 141. Rebuild (`REINDEX`) after large data changes |

## Fault 2: `ivfflat.probes = 1`

| | |
|---|---|
| Root cause | A query only searches the `probes` nearest lists. With 1 of 141, a neighbour just across a cluster boundary is missed |
| Fix | `ALTER ROLE trail_desk_app SET ivfflat.probes = 12` (≈ √lists). It's a role setting, so every Data API session of the app identity gets it |

## Fault 3: `hnsw.ef_search` (40) is lower than `LIMIT 100`

| | |
|---|---|
| Root cause | An HNSW index scan returns at most `ef_search` rows. `LIMIT 100` silently returns 40 |
| Fix | `ALTER ROLE trail_desk_app SET hnsw.ef_search = 200` (≥ LIMIT, with headroom for recall). With pgvector ≥ 0.8 (Aurora PostgreSQL 16.6+), `hnsw.iterative_scan` can also continue scanning when filters remove rows |

## Debrief answers

1. An ANN index always returns *something* quickly. Only comparing against exact (brute-force) results tells you whether it's the *right* something.
   Keep a recall benchmark in CI.
2. IVFFlat builds faster and uses less memory, so it suits large, mostly static data that's rebuilt periodically. HNSW gives better recall and speed,
   handles inserts without a rebuild, but has slower, memory-hungry builds. HNSW is the default choice today.
3. Filters are applied **after** the index scan. If only 5 % of rows match, an `ef_search` of 40 yields ~2 rows. Use iterative scans,
   a larger `ef_search`, partial indexes, or partitioning per tenant.
4. Raise `lists` (IVFFlat) or `m`/`ef_construction` (HNSW) as the data grows, give builds enough `maintenance_work_mem`, rebuild IVFFlat after
   distribution shifts, monitor recall continuously, and consider smaller or quantised vectors (`halfvec`, dimension reduction) to keep the index in memory.
