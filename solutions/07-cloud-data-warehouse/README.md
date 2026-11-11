# Lab 07 solution: Cloud Data Warehouse

SQL: [`01_schema.sql`](01_schema.sql), [`02_load.sql`](02_load.sql), [`03_queries.sql`](03_queries.sql).
`solve.sh` runs them through the Redshift Data API. You can also paste them into
**Query Editor v2**: connect to workgroup `cq-da-07` with *AWS Secrets Manager* or *Federated user*.

## Design choices

| Choice | Why |
|---|---|
| Star schema (`fact_sales` + `dim_customer`, `dim_product`) | Analysts slice by customer and product attributes; dimensions change slowly |
| `DISTSTYLE ALL` on the dimensions | They're tiny. Copying them to every compute slice makes every join local, with no network redistribution |
| `DISTKEY(customer_id)` on the fact table | Spreads rows evenly (500 customers) and co-locates per-customer aggregations |
| `COMPOUND SORTKEY(order_date, region)` | Most queries filter on a date range, then a region. Zone maps let Redshift skip blocks |
| Load to `stg_orders`, then `INSERT … SELECT` | COPY can't compute columns. ELT inside the warehouse derives `order_date` and can validate or deduplicate first |
| 4 gzip files | COPY loads files in parallel across slices. Aim for a multiple of the slice count, with files of similar size |
| `PRIMARY KEY` / `REFERENCES` | **Not enforced** by Redshift. They're hints to the planner, and documentation for people |

Redshift Serverless also offers *automatic table optimization* (`DISTSTYLE AUTO`,
`SORTKEY AUTO`). Choosing the keys yourself is the exam-relevant skill, and it lets you see the effect with `EXPLAIN`.

## Spectrum

`CREATE EXTERNAL SCHEMA … FROM DATA CATALOG` maps a Glue database into
Redshift. The 2023 archive is never loaded. Redshift Spectrum scans it in S3 and
bills $5/TB scanned, so older, rarely used data stays cheap. Convert the
archive to Parquet and partition it to cut scan costs, the same way you did in Lab 02.

## Materialized view

`AUTO REFRESH YES` makes Redshift refresh the view incrementally in the
background after base-table changes, when it can. Dashboards query the
small pre-aggregated table instead of scanning 200k fact rows.
`SELECT * FROM SVV_MV_INFO` shows its state.

## Cost guard-rails (task 7)

- **Usage limit** on the workgroup: RPU-hours per day/week/month, with the action
  `log`, `emit-metric` or `deactivate`. Deactivate blocks new queries until the period ends.
- **Max capacity** caps how far the workgroup scales up for one heavy query.
- Serverless bills nothing while idle, but storage is billed continuously, so delete the stack when you've finished.
