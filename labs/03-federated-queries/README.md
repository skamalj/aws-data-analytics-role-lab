# Lab 03: Federated Queries

## Scenario

Riverbend's marketing team keeps customer profiles in an **Amazon DynamoDB**
table that the CRM app writes to: loyalty points, marketing opt-in and
preferred channel. Orders live in the S3 data lake. Marketing wants a
campaign list that joins the two. They want it without a nightly ETL job copying
DynamoDB into S3, and without hitting the production table any harder than needed.

Use **Athena Federated Query** to query DynamoDB in place with SQL, join it
to the lake, and export the result to S3.

## What the starting environment gives you

`./scripts/deploy.sh 03-federated-queries` creates:

| Resource | Output | Notes |
|---|---|---|
| DynamoDB table `riverbend_customer_profiles` | `DynamoDBTable` | 500 items, partition key `customer_id` |
| Lake bucket | `LakeBucket` | `orders/orders_2024_h1.csv` |
| Glue database `riverbend_fed`, table `orders` | `GlueDatabase` | Already cataloged |
| Spill bucket | `SpillBucket` | For connector results too large for a Lambda response |
| Athena workgroup `cq-da-03` (engine v3) | `AthenaWorkGroup` | |

DynamoDB item shape:

```json
{"customer_id": "C00001", "full_name": "Quinn Moreau", "email": "...", "region": "LATAM",
 "loyalty_tier": "bronze", "loyalty_points": 312, "marketing_opt_in": true,
 "preferred_channel": "sms", "last_login": "2024-03-04"}
```

## Your tasks

1. **Deploy the Amazon Athena DynamoDB connector** from the AWS Serverless
   Application Repository (application `AthenaDynamoDBConnector`, published by AWS):
   - Lambda function / catalog name: `riverbend-ddb`
   - Spill bucket: `SpillBucket`
2. **Register an Athena data source** (data catalog) of type Lambda named
   `ddb`, pointing to the `riverbend-ddb` function.
3. **Explore**: list the tables visible through `ddb` and run
   `SELECT * ... LIMIT 10` on the profiles table.
4. **Answer:**
   1. Per `loyalty_tier`: the number of customers and the number who have opted in to marketing.
   2. The **campaign list**: the top 10 opted-in customers by completed
      revenue in the S3 orders, with name, email, tier and revenue.
      This query joins DynamoDB and S3.
   3. How many opted-in **gold or platinum** customers are in the `EU` region?
5. **Export**: write the full campaign list (every opted-in customer with at least
   one completed order, not just the top 10) to
   `s3://<LakeBucket>/exports/campaign_list/` as Parquet, using one CTAS
   statement. Name the table `riverbend_fed.campaign_list`.

## How you know you're done

- In the Athena editor, data source `ddb`, database `default` shows the table `riverbend_customer_profiles`.
- `SELECT COUNT(*) FROM riverbend_fed.campaign_list` returns the value in
  [`expected-results.md`](../../solutions/03-federated-queries/expected-results.md), as do your task 4 answers.

## Hints

<details><summary>Naming</summary>
Federated tables are addressed as <code>"catalog"."schema"."table"</code>. The DynamoDB
connector exposes all tables under the schema <code>default</code>, which is a reserved
word, so quote it: <code>ddb."default".riverbend_customer_profiles</code>.
</details>

<details><summary>Predicate push-down</summary>
Filters on the partition key (and some other filters) are pushed down to DynamoDB. Everything else
is a full table Scan. Check the connector's CloudWatch logs to see which it did.
</details>

## DIY challenge

- Make a view in `riverbend_fed` that hides the federated join from analysts.
  Note that Athena views can reference federated catalogs.
- Add a second connector (for example the CloudWatch Logs connector) and query
  the DynamoDB connector's own Lambda logs with SQL.

## Cleanup

```bash
./solutions/03-federated-queries/cleanup.sh      # removes the connector stack, data catalog, CTAS table
./scripts/destroy.sh 03-federated-queries
```

**Cost:** under $0.10. On-demand DynamoDB reads, Lambda invocations and small Athena scans.
