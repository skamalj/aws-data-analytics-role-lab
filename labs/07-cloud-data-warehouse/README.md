# Lab 07: Cloud Data Warehouse

## Scenario

Finance wants sub-second dashboards and complex joins over a full year of
sales, plus a simple way to query older history kept in S3, without paying
to load it. Riverbend chooses **Amazon Redshift Serverless**: no clusters to size,
and billing only while queries run.

## What the starting environment gives you

`./scripts/deploy.sh 07-cloud-data-warehouse` creates:

| Resource | Notes |
|---|---|
| Redshift Serverless namespace + workgroup `cq-da-07` | Database `riverbend`, admin user `awsadmin`. **The password is in Secrets Manager**, managed by Redshift |
| IAM role `cq-da-07-redshift-role` | The namespace's **default** role: S3 read on the staging bucket, Glue catalog read |
| `StagingBucket` | `stage/orders/*.csv.gz` (200k 2024 orders in 4 gzip files), `stage/customers/`, `stage/products/` |
| | `archive/orders_2023/` (50k orders, CSV) |
| Glue database `riverbend_archive`, table `orders_2023` | Catalog entry over the archive |

> **Cost:** about $3 per hour of *active* query time at 8 RPU (60-second
> minimum per burst). Idle time is free. New accounts get Redshift Serverless
> free-trial credit. Destroy the stack when you've finished.

## Your tasks

1. Connect with **Query Editor v2** to workgroup `cq-da-07`, database `riverbend`.
2. **Design and create a star schema**: `dim_customer`, `dim_product` and
   `fact_sales`. `fact_sales` needs an `order_date DATE` column as well as
   `order_ts`. Choose distribution styles and sort keys, and be ready to justify them.
3. **Load the data** with `COPY` using the namespace's default IAM role. Load the
   orders into a staging table first, then populate `fact_sales` with SQL.
   Confirm there are 200,000 fact rows and no load errors.
4. **Report:** completed revenue per quarter per category for 2024, and the quarter totals.
5. **Query the archive in place.** Create an external schema `archive` over
   the Glue database `riverbend_archive` (Redshift Spectrum), then find the
   **top 5 customers by lifetime completed revenue** across 2023 *and* 2024.
6. Create a **materialized view** `mv_daily_region_sales` (order_date, region,
   orders, revenue for completed orders) that refreshes automatically. Query it for 2024-07-04.
7. **Guard-rail:** add a usage limit to the workgroup of 4 RPU-hours per day that emits a CloudWatch metric when breached.

## How you know you're done

Values match [`expected-results.md`](../../solutions/07-cloud-data-warehouse/expected-results.md).

## Hints

<details><summary>COPY options</summary><code>FORMAT AS CSV IGNOREHEADER 1 GZIP TIMEFORMAT 'YYYY-MM-DD HH:MI:SS'</code>, and <code>IAM_ROLE default</code>. Load errors are in <code>sys_load_error_detail</code>.</details>
<details><summary>Spectrum types</summary>The archive's <code>total_amount</code> is <code>double</code>. Cast it to <code>DECIMAL(12,2)</code> before you <code>UNION ALL</code> it with the fact table.</details>

## DIY challenge

- Run `EXPLAIN` on the 4.1 query and look for `DS_BCAST_INNER` vs `DS_DIST_NONE`. Then change `dim_product` to `DISTSTYLE EVEN` and compare.
- `UNLOAD` the lifetime top-100 list to S3 as Parquet.
- Create a read-only database role for analysts, and grant it to an IAM-federated user.

## Cleanup

```bash
./scripts/destroy.sh 07-cloud-data-warehouse
```
