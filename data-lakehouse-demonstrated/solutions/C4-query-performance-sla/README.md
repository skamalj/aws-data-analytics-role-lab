# Challenge C4 solution: The dashboard is too slow

```bash
patch -p1 < solutions/C4-query-performance-sla/fix.patch     # writes sql/maintenance.sql and rewrites sql/dashboard.sql
python3 missions/C4-query-performance-sla/scenarios/run_maintenance.py
python3 missions/C4-query-performance-sla/scenarios/check.py
```

Verified locally with Spark + Iceberg (the same loader at 1/50 scale): the loader leaves 160 files per partition per batch, ~36,000 files of
~3 KB–130 KB at full scale. After the fix there are 90 files (one per day) and 1 snapshot, with identical query results.

| # | Fault | Fix |
|---|---|---|
| 1 | **Small files.** The loader wrote with `write.distribution-mode = none` from 40 tasks into all 90 daily partitions, in 10 appends: ~36,000 tiny files. Athena spends its time opening files and reading metadata, not data | Compact: Spark `CALL system.rewrite_data_files(… strategy => 'binpack')`, or Athena `OPTIMIZE riverbend_lakehouse.sales REWRITE DATA USING BIN_PACK` (repeat until done). Set `write.distribution-mode = hash` so future writes produce one file per partition per write |
| 2 | **The table property makes compaction useless.** `write_target_data_file_size_bytes = 131072` (128 KB). Every writer, *including compaction*, targets 128 KB files, so a "successful" rewrite still leaves ~15,000 files | `write.target-file-size-bytes = 536870912` (512 MB), **before** compacting |
| 3 | **No pruning.** `date_format(sold_at, '%Y-%m') = '2026-03'` and `format_datetime(...)` hide the partition column inside a function, so every partition is read | Range predicates on the source column: `sold_at >= TIMESTAMP '2026-03-01 00:00:00' AND sold_at < TIMESTAMP '2026-04-01 00:00:00'`. Iceberg maps them onto `day(sold_at)` |
| 4 | **History.** 10+ snapshots keep the old small files alive, and planning walks their manifests | `CALL system.expire_snapshots(…, retain_last => 1)`, or Athena `VACUUM riverbend_lakehouse.sales` with `vacuum_max_snapshot_age_seconds` |

Expected answers (unchanged by the fix): Q1 NA 473,927,277.23 · EU 467,457,157.13 · LATAM 431,496,039.08 · APAC 421,577,113.98.
Q2: P106, P114, P118. Q3: 1,124,387.56 from 4,444 sales.

**Operational follow-up:** schedule compaction (Glue Data Catalog **table optimizers** can compact, expire snapshots and remove orphan files
automatically for Iceberg tables), and make streaming writers batch larger.
