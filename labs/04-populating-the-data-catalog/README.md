# Lab 04: Populating the Data Catalog

## Scenario

Three teams now deliver files into a shared **landing bucket**, and each does
it differently:

| Folder | Producer | Format quirks |
|---|---|---|
| `web_orders/year=YYYY/month=MM/` | e-commerce export job | JSON Lines, Hive-style partitions, writes an empty `_SUCCESS` marker. Someone also left a stray CSV `*.tmp` file in one partition |
| `store_sales/` | point-of-sale system | **pipe-delimited**, **no header row**. Columns are `order_id, order_ts, store_id, product_id, quantity, total_amount` |
| `returns/` | returns desk | CSV with header. Some files are **gzip-compressed** (`.csv.gz`) |
| `clickstream/YYYY/MM/DD/` | web analytics | JSON Lines in date folders that are **not** `key=value` |

Analysts complain that the catalog is a mess: odd column names, dozens of
tables named after partitions, and missing days. Build a clean, automated
**Glue Data Catalog** for the landing zone.

## What the starting environment gives you

`./scripts/deploy.sh 04-populating-the-data-catalog` creates the
`LandingBucket` (seeded with Jan–Jun 2024), an Athena workgroup `cq-da-04`
and a Glue role `cq-da-04-glue-crawler-role`.

## Your tasks

1. Create a Glue database `riverbend_catalog`.
2. Create **one** crawler `cq-da-04-landing-crawler` that:
   - crawls `web_orders/`, `store_sales/` and `returns/` (three S3 targets)
   - names tables with the prefix `lnd_`, so you get `lnd_web_orders`, `lnd_store_sales` and `lnd_returns`
   - **ignores** the `_SUCCESS` markers and any `*.tmp` files
   - produces proper column names for the pipe-delimited POS files
3. Run it and check:
   - `lnd_web_orders` has partition keys `year` and `month` and 6 partitions,
     with no extra tables such as `lnd_month_03` or `lnd_year_2024`
   - `lnd_store_sales` has the six named columns
   - `lnd_returns` includes rows from **both** the plain and the gzip file
4. **Clickstream without a crawler.** Write an Athena DDL statement that creates
   `riverbend_catalog.clickstream` over `clickstream/`, with a partition column
   `dt` (type `date`) and **partition projection**, so new days are queryable
   immediately with no crawler run and no `MSCK REPAIR`/`ALTER TABLE ADD PARTITION`.
5. Query: count clickstream events by `event_type` for `2024-06-03`.
6. **Automate.** Give the crawler a daily schedule (03:00 UTC) and set it to
   **crawl new folders only**. Then simulate the next delivery:
   ```bash
   python3 labs/04-populating-the-data-catalog/infra/add_month.py
   ```
   Re-run the crawler and confirm that partition `month=07` appeared without the existing
   partitions being re-crawled.

## How you know you're done

Row counts and answers match [`expected-results.md`](../../solutions/04-populating-the-data-catalog/expected-results.md).

## Hints

<details><summary>Exclusions</summary>Crawler exclude patterns are glob patterns relative to the include path, for example <code>**.tmp</code>.</details>
<details><summary>Headerless files</summary>A custom CSV classifier can set the delimiter, say the header is absent, and supply the column names.</details>
<details><summary>Projection</summary>Look at the table properties <code>projection.enabled</code>, <code>projection.dt.type=date</code> and <code>storage.location.template</code>.</details>

## DIY challenge

- Add a Glue **Data Quality** ruleset to `lnd_store_sales` (for example, `quantity > 0` and `order_id` unique).
- Turn on the crawler's *Create a single schema for each S3 path* option and see how it behaves differently.

## Cleanup

```bash
./solutions/04-populating-the-data-catalog/cleanup.sh
./scripts/destroy.sh 04-populating-the-data-catalog
```

**Cost:** a few cents in crawler runtime.
