# Lab 12 solution: Business Intelligence with Amazon QuickSight

[`template.yaml`](template.yaml) creates the data source, the SPICE dataset (with calculated
fields and geographic roles), the row-level-security dataset and a daily refresh schedule.
`QS_AUTHOR=<you> QS_READER=<reader> ./solve.sh` deploys it.
The **analysis and dashboard** are built in the console, as described below.

## 0. One-time QuickSight setup

1. Subscribe to QuickSight (Enterprise edition is needed for RLS), in the **same region** as the lab.
2. **Manage QuickSight > Security & permissions > AWS resources**: tick **Amazon Athena** and,
   under **Amazon S3**, the `cq-da-12-lake-…` bucket **and** the `cq-da-12-athena-…` results bucket
   (QuickSight writes Athena query results there).
3. Optional reader: **Manage users > Invite users**, role *Reader*.

## 1. Data source and dataset

**Datasets > New dataset > Athena**: workgroup `cq-da-12`, catalog `AwsDataCatalog`,
database `riverbend_bi`, table `v_sales`, **Import to SPICE**. Then **Edit dataset**:
- Add calculated field `completed_revenue = ifelse({status} = 'COMPLETED', {total_amount}, 0)`
- Set the data type of `country` to *Geospatial > Country*, and `city` to *City*

Why SPICE? It's an in-memory engine. Dashboards don't run an Athena query (and bill a
scan) on every page load, and visuals respond in milliseconds. Use *Direct query* only
when the data must be fresh to the minute.

## 2. Analysis (task 3)

| Visual | Field wells |
|---|---|
| KPI | Value: `completed_revenue` (sum). Trend group: `order_date` (MONTH). Shows the latest month vs the previous one |
| Line chart | X: `order_date` (MONTH). Value: `completed_revenue`. Color: `channel` |
| Horizontal bar | Y: `category`. Value: `completed_revenue`, sorted descending |
| Filled map | Location: `country`. Color: `completed_revenue` |
| Table | `product_name`, `completed_revenue`, `quantity`, with a top-10 filter on `product_name` by `completed_revenue` |
| Control | Filter on `region`, **added to the sheet** as a drop-down control, applied to all visuals |

**Share > Publish dashboard**: *Riverbend Sales Overview*. Then share it with the reader.

## 3. Row-level security (task 4)

`rls_rules` (S3 → Glue → Athena → SPICE) has the columns `UserName` and `region`. Attached to
the sales dataset with *Grant access*, each QuickSight user only sees rows whose `region`
matches one of their rule rows. The author has a row for every region, and the reader has only `EU`.
A user with **no** rule rows sees **no** data. That's safer than "see everything".

This complements Lab 06. Lake Formation controls what the *query engine* returns. QuickSight
RLS controls what each *dashboard viewer* sees in data that's already in SPICE.

## 4. Refresh (task 5)

The `daily-full-refresh` schedule re-imports SPICE at 02:15 UTC.
**Datasets > Riverbend sales 2024 > Refresh** shows the history, and *Refresh now* triggers one manually.
