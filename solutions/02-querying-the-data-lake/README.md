# Lab 02 solution: Querying the Data Lake

`./solutions/02-querying-the-data-lake/solve.sh` runs everything. All the SQL is in [`queries.sql`](queries.sql).

## Why Parquet and partitions cut the scan

| Technique | Effect on the task 1 query |
|---|---|
| Columnar format (Parquet) | Athena reads only `status`, `region` and `total_amount`, not all 12 columns |
| Compression (Snappy) | Fewer bytes on disk for the columns it does read |
| Partitioning by year/month | Athena skips 11 of the 12 month folders entirely, because `order_month = 3` is resolved from the catalog |
| Row-group statistics | Parquet min/max statistics let it skip row groups for the `region` filter too |

Together these take the scan from ~16 MB to a few hundred KB, a reduction of
more than 95%. Athena bills per byte scanned, so cost drops by the same factor.

## CTAS details

- `external_location` must point to an **empty** prefix, otherwise CTAS fails.
  To re-run, drop the table **and** delete the S3 prefix. Dropping an external table doesn't delete its data.
- Partition columns go last in the SELECT.
- A CTAS (or `INSERT INTO`) can write at most 100 partitions per statement.
  For daily partitions over several years, load in batches with `INSERT INTO`.

## View

A view stores the query, not data, so it always reflects the current Parquet
table. It uses `LEFT JOIN` so an order with an unknown product or customer
still appears. Make sure analysts filter on `order_year`/`order_month`: the
filters are pushed down through the view, so partition pruning still works.

## Workgroup guard-rail (console)

Athena, **Workgroups > Create workgroup**:
- Query result location `s3://<AthenaResultsBucket>/analysts/`
- Tick **Override client-side settings**
- **Per query data usage control**: 10 MB, action *Cancel query*

Per-query limits cancel the query that crosses the threshold. Per-workgroup
limits (hourly or daily totals) only raise an SNS alarm and can't cancel queries.
Use IAM to stop analysts from switching back to the unrestricted workgroup
(`athena:StartQueryExecution` on the workgroup ARN).
