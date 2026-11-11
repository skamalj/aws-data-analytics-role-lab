# Lab 02: Querying the Data Lake

## Scenario

The data lake from Lab 01 is a success, and now the whole year of orders
(200,000 rows, 12 monthly CSV files) sits in S3. Analysts run the same
"revenue for one region in one month" queries all day. Every query scans
every CSV file, so the Athena bill keeps growing and queries are slow.

Riverbend's data lead asks you to:
1. Build a **curated**, columnar, partitioned copy of the orders data.
2. Prove with numbers that queries on it scan far less data.
3. Give analysts a simple view to query.
4. Put a guard-rail in place so that no single analyst query can scan more than 10 MB.

## What the starting environment gives you

`./scripts/deploy.sh 02-querying-the-data-lake` creates:

| Resource | Output | Notes |
|---|---|---|
| Raw bucket | `RawBucket` | `orders/orders_2024-MM.csv` (12 files, ~16 MB), `customers/`, `products/` |
| Curated bucket | `CuratedBucket` | Empty. Your Parquet data goes here |
| Athena results bucket | `AthenaResultsBucket` | |
| Athena workgroup | `cq-da-02` | No data limits |
| Glue database `riverbend_lake` | `GlueDatabase` | Tables `orders_csv`, `customers`, `products` already defined |

## Your tasks

1. **Baseline.** In workgroup `cq-da-02`, query the `COMPLETED` revenue and
   order count for region `EU` in March 2024, using `orders_csv`. Write down
   the *Data scanned* figure.
2. **Create a curated table** `riverbend_lake.orders_parquet` using a single
   Athena **CTAS** statement:
   - Format Parquet, compression Snappy
   - Location `s3://<CuratedBucket>/orders_parquet/`
   - Partitioned by two integer columns, `order_year` and `order_month`, derived from `order_ts`
   - All the original columns kept
3. **Prove it.** Run the task 1 question against `orders_parquet`, filtering on
   the partition columns. Data scanned must be under 5% of the baseline.
4. **Create a view** `riverbend_lake.v_order_details` with one row per order,
   adding the product name and category plus the customer's country and
   loyalty tier. Build it on `orders_parquet`.
5. **Answer with the view:**
   1. Completed revenue per product category for 2024.
   2. The top 3 customer countries by completed revenue in December 2024.
6. **Guard-rail.** Create a workgroup `cq-da-02-analysts` that:
   - writes results to `s3://<AthenaResultsBucket>/analysts/`
   - enforces its settings, so clients can't override them
   - cancels any query that scans more than **10 MB**

   Show that the task 1 query on `orders_csv` is cancelled in this workgroup,
   while the same query on `orders_parquet` succeeds.

## How you know you're done

- `SHOW PARTITIONS riverbend_lake.orders_parquet` returns 12 partitions.
- The CSV query fails in `cq-da-02-analysts` with a "data limit exceeded" error.
- Your answers match [`solutions/02-querying-the-data-lake/expected-results.md`](../../solutions/02-querying-the-data-lake/expected-results.md).

## Hints

<details><summary>CTAS rules</summary>
In <code>WITH (partitioned_by = ARRAY[...])</code>, the partition columns must be the
<b>last</b> columns in the SELECT list, in the same order. A single CTAS can create
at most 100 partitions.
</details>

<details><summary>Workgroup limit</summary>
Look for "Data usage controls" in the workgroup settings
(<code>BytesScannedCutoffPerQuery</code> in the API). 10 MB is the smallest value allowed.
</details>

## DIY challenge

- Use `INSERT INTO orders_parquet SELECT ...` to load one more month of data
  that you generate yourself.
- Try `bucketed_by = ARRAY['customer_id']` and compare the scans when filtering on one customer.
- Convert `orders_parquet` to an Apache Iceberg table (`table_type = 'ICEBERG'`)
  and run an `UPDATE` that marks one order `RETURNED`.

## Cleanup

```bash
./solutions/02-querying-the-data-lake/cleanup.sh
./scripts/destroy.sh 02-querying-the-data-lake
```

**Cost:** under $0.05. The full-CSV scans are about 16 MB each.
