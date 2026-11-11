# Lab 12: Business Intelligence with Amazon QuickSight

## Scenario

All the work so far ends in SQL. Riverbend's leadership wants a **self-service
dashboard** instead: revenue trend, channel mix, best products and a world map.
Regional managers must only ever see **their own region**. The dashboard must load
instantly and refresh nightly.

## What the starting environment gives you

`./scripts/deploy.sh 12-business-intelligence-quicksight` creates:

| Resource | Notes |
|---|---|
| `LakeBucket` | 2024 orders (200k rows), customers, products, as CSV |
| Glue database `riverbend_bi` | Tables `orders`, `customers`, `products`, and the view **`v_sales`** (orders joined with product and customer attributes) |
| Athena workgroup `cq-da-12` | Writes to `cq-da-12-athena-…` |

> **Prerequisite and cost:** QuickSight is a subscription service. New
> accounts usually get a free trial for a few authors. After that it's billed per user per month.
> **Enterprise edition** is needed for row-level security. If you don't want to keep
> it, unsubscribe at the end (Manage QuickSight > Account settings).

## Your tasks

0. Subscribe to QuickSight in the lab's region, and give it access to Athena and the two `cq-da-12-*` buckets.
1. Create an **Athena data source** that uses workgroup `cq-da-12`.
2. Create a dataset **Riverbend sales 2024** from `riverbend_bi.v_sales`, imported into **SPICE**, with:
   - a calculated field `completed_revenue` (the order total for `COMPLETED` orders, otherwise 0)
   - `country` and `city` recognised as geographic fields
3. Build an **analysis** with:
   - a KPI of completed revenue, with this month vs last month
   - monthly revenue by channel (line)
   - revenue by category (bar)
   - revenue by country (filled map)
   - top-10 products (table)
   - a **region** drop-down control that filters every visual
4. **Row-level security:** make sure a reader user only ever sees `EU` data, whatever filters they pick.
   Keep the rules in the data lake (S3 + Glue), not typed into QuickSight by hand.
5. Publish the dashboard **Riverbend Sales Overview**, share it with the reader, and schedule a **daily SPICE refresh**.
6. Question: when would you use *Direct query* instead of SPICE?

## How you know you're done

Visual values match [`expected-results.md`](../../solutions/12-business-intelligence-quicksight/expected-results.md).
Signed in as the reader, the KPI shows 7,890,826.45 (EU only).

## Hints

<details><summary>QuickSight says it can't access the bucket / Athena results</summary>Manage QuickSight > Security & permissions. Both the data bucket and the Athena results bucket must be ticked.</details>
<details><summary>RLS rules format</summary>A dataset with a <code>UserName</code> (or <code>GroupName</code>) column and one column per field to restrict, here <code>region</code>. Several rows for the same user are combined (OR).</details>

## DIY challenge

- Add a **Redshift** data source (Lab 07) and compare SPICE refresh times.
- Use **Amazon Q in QuickSight** (topics) so managers can ask "revenue by channel last quarter".
- Embed the dashboard in a web page using the QuickSight embedding SDK.

## Cleanup

```bash
./solutions/12-business-intelligence-quicksight/cleanup.sh
./scripts/destroy.sh 12-business-intelligence-quicksight
```
