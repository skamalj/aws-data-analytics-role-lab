# Lab 04 solution: Populating the Data Catalog

`./solutions/04-populating-the-data-catalog/solve.sh` runs every step.

## Crawler design

| Requirement | Setting |
|---|---|
| One crawler, three datasets | Three **S3 targets**. Each include path becomes its own table root |
| `lnd_` names | **Table prefix** `lnd_` |
| Ignore junk | **Exclude patterns** `**.tmp` and `**_SUCCESS` on the `web_orders/` target |
| Headerless pipe files | Custom **CSV classifier**: delimiter `|`, header *absent*, column names supplied |
| Partitions | Nothing to configure. `key=value` folders become partition keys `year` and `month` |
| Gzip | Nothing to configure. Crawlers and Athena read `.gz` transparently |

### Why the `.tmp` file matters

If the crawler isn't told to skip it, it finds a CSV file among JSON files in
`month=03`. Their schemas differ too much to be one table, so the crawler stops
treating `web_orders/` as a single table and creates a table per folder
(`lnd_month_01`, and so on). Even if it did merge them, Athena would try to read the CSV
rows as JSON and fail or return garbage. Exclusions prevent both problems. A safer
pattern still is to have producers write to a temporary prefix and *move* files
in when they're complete.

### Classifier ordering

Custom classifiers are evaluated in the order listed on the crawler, before
the built-in ones. The first classifier that recognises a file with certainty
1.0 wins. The pipe classifier doesn't match the comma-delimited returns files
or the JSON files, so those fall back to the built-in classifiers.

## Partition projection vs crawlers

`clickstream/2024/06/03/` isn't `key=value`, so a crawler would produce
`partition_0`, `partition_1` and `partition_2` string columns, and each new day would
need another crawl. With **partition projection**, Athena computes partition
locations from the table properties at query time:

```
projection.dt.type          = date
projection.dt.format        = yyyy/MM/dd
storage.location.template   = s3://bucket/clickstream/${dt}/
```

There are no partitions in the catalog at all, and new days are queryable
the moment the files land. Projection is often faster than catalog look-ups
for tables with very many partitions. Note that projection is used by **Athena**. Glue ETL
jobs and Redshift Spectrum don't apply it.

## Incremental crawls

`RecrawlPolicy = CRAWL_NEW_FOLDERS_ONLY` makes the crawler list only S3
folders added since the last run. Glue requires the schema-change policy to be
`LOG` for both updates and deletes when this is on. That's why `solve.sh`
changes the policy at the same time. For event-driven catalog updates, look at
**S3 event-based crawls** (`CRAWL_EVENT_MODE` with an SQS queue), which is a good follow-up exercise.
