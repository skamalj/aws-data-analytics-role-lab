# Lab 01 solution: Data Lakes

Run everything at once with `./solutions/01-data-lakes/solve.sh`, or follow the
steps below in the console.

## 1. Glue database

Glue console, **Data Catalog > Databases > Add database**, name `riverbend_raw`.

```bash
aws glue create-database --database-input Name=riverbend_raw
```

## 2. Crawler

**Crawlers > Create crawler**
- Name `cq-da-01-raw-crawler`
- Data source: S3, path `s3://<RawBucket>/sales/`, *crawl all sub-folders*
- IAM role: choose existing `cq-da-01-glue-crawler-role`
- Output: database `riverbend_raw`, no table prefix
- Schedule: on demand. Then **Run crawler**.

The crawler creates one table per folder because each folder holds files with a
different schema: `orders`, `customers` and `products`.

## 3. Why `customers` has `col0 … col9`

Glue's built-in CSV classifier only treats the first row as a header when the
header **looks different from the data**. Typically that means every header
value is a string and at least one data column is not. `orders` has numeric
columns (`quantity`, `total_amount`), so its header is detected. In
`customers` every column is text, so the classifier can't tell the header from
the data and uses generic names.

**Fix:** create a custom CSV classifier with **Column headings = Has headings**
(`ContainsHeader=PRESENT`), attach it to the crawler, delete the bad
`customers` table and run the crawler again.

```bash
aws glue create-classifier --csv-classifier \
  "Name=cq-da-01-csv-with-header,Delimiter=',',QuoteSymbol='\"',ContainsHeader=PRESENT"
aws glue update-crawler --name cq-da-01-raw-crawler --classifiers cq-da-01-csv-with-header
aws glue delete-table --database-name riverbend_raw --name customers
aws glue start-crawler --name cq-da-01-raw-crawler
```

Custom classifiers are tried before the built-in ones. `products.json` doesn't
match a CSV classifier, so the built-in JSON classifier still handles it.

Another fix would be to edit the schema by hand. That works, but the next
crawler run overwrites it unless you change the schema-change policy, so the
classifier is the better fix.

## 4. Queries

See [`queries.sql`](queries.sql). Points to note:
- Filter on `status = 'COMPLETED'` *before* aggregating.
- 4.2 needs a join to `products` to get the name.
- 4.4 uses a `LEFT JOIN` to a per-customer subtotal. Joining raw orders
  straight to customers and averaging `total_amount` would give the average
  *order* value, not the average revenue per customer.

## 5. Saved query

Athena editor, **Save > Save as**, name `revenue-by-region`. Or use `aws athena create-named-query` (see `solve.sh`).

## What you learned

- A data lake is storage (S3), a catalog (Glue Data Catalog) and query engines
  (Athena and others) that read the data where it sits.
- Crawlers infer schemas, and they can infer them wrongly. Check what they produce.
- Athena workgroups set the result location and can enforce settings and
  limits (used in Lab 02).
