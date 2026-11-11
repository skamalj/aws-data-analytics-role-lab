# Lab 01: Data Lakes

## Scenario

Riverbend Outfitters sells outdoor gear in stores and online in four regions
(NA, EU, APAC, LATAM). Every night its order system, CRM and product system
each drop an export file into Amazon S3. The finance team wants answers from
those files without loading them into a database first, and they want to use
plain SQL.

Your job is to turn the raw bucket into a basic, queryable **data lake**:
catalog the files with AWS Glue and query them with Amazon Athena.

## What the starting environment gives you

`./scripts/deploy.sh 01-data-lakes` creates:

| Resource | Name (stack output) | Notes |
|---|---|---|
| S3 bucket with raw exports | `RawBucket` | `sales/orders/*.csv`, `sales/customers/*.csv`, `sales/products/*.json` (JSON Lines) |
| S3 bucket for query results | `AthenaResultsBucket` | Objects expire after 7 days |
| Athena workgroup | `AthenaWorkGroup` (`cq-da-01`) | Already writes results to the bucket above |
| IAM role for Glue | `GlueCrawlerRoleName` | Can read `RawBucket` and write to the Data Catalog |

```
 exports ──► s3://<RawBucket>/sales/{orders,customers,products}/
                         │
                  (you build) Glue crawler ──► Glue Data Catalog db: riverbend_raw
                                                         │
                                         (you query) Athena workgroup cq-da-01
```

## Your tasks

1. **Create a Glue database** named `riverbend_raw`.
2. **Create and run a Glue crawler** named `cq-da-01-raw-crawler`:
   - Data source: `s3://<RawBucket>/sales/`
   - IAM role: the role from `GlueCrawlerRoleName`
   - Target database: `riverbend_raw`
   - Run it on demand.
   - When it finishes, the database should have exactly three tables:
     `orders`, `customers` and `products`.
3. **Inspect the schemas.** One of the three tables will look wrong: its
   columns are named `col0`, `col1`, ... and the header row appears as data.
   Work out why the crawler did this, then fix it so the table has proper
   column names (`customer_id`, `first_name`, ...). Do not edit the data file.
4. **Answer these questions in Athena** (use workgroup `cq-da-01`). Only count
   orders whose `status` is `COMPLETED`:
   1. Total revenue (`total_amount`) and number of orders per region, highest
      revenue first.
   2. The top 5 products by revenue, showing the product **name** and category.
   3. Revenue per calendar month.
   4. For each `loyalty_tier`: the number of customers, and their average
      revenue per customer.
5. **Save** query 4.1 as a saved query (named query) called `revenue-by-region`.

## How you know you're done

- `aws glue get-tables --database-name riverbend_raw` lists three tables, and
  `customers` has named columns.
- Your answers match the check values in
  [`solutions/01-data-lakes/expected-results.md`](../../solutions/01-data-lakes/expected-results.md).
  Try not to open the rest of the solution folder until you're done.

## Hints

<details><summary>Hint for task 3</summary>
Look at the column types the crawler inferred for <code>orders</code> versus
<code>customers</code>. How does the built-in CSV classifier decide whether the first
row is a header? Glue lets you create your own classifiers.
</details>

<details><summary>Hint for task 4.3</summary>
<code>order_ts</code> may be cataloged as a string. <code>date_trunc('month', CAST(order_ts AS timestamp))</code> works either way.
</details>

## DIY challenge

- Give the crawler a schedule (daily at 02:00 UTC) and set its schema-change
  policy to *log* rather than *update* changes.
- Upload a second orders file with an extra column and see what the crawler does.

## Cleanup

```bash
./solutions/01-data-lakes/cleanup.sh   # removes the crawler, classifier, database, saved query
./scripts/destroy.sh 01-data-lakes
```

**Cost:** a few cents. Glue crawler runs are billed per DPU-hour (check the
current minimum per run on the Glue pricing page), and Athena bills $5 per TB scanned.
This dataset is under 1 MB.
