# Lab 03 solution: Federated Queries

`./solutions/03-federated-queries/solve.sh` does everything below.

## How Athena Federated Query works

```
Athena engine ──(Lambda invoke)──► riverbend-ddb connector ──► DynamoDB Scan/Query
      │                                   │
      │                                   └─ large results ──► s3://<SpillBucket>/athena-spill/
      └── joins with S3 data via the Glue catalog (riverbend_fed.orders)
```

A connector is a Lambda function built on the Athena Query Federation SDK.
Athena asks it for the table list, the schema, the *splits* (units of parallel
work) and then the data. It returns Apache Arrow record batches, and results too large for a Lambda
response are written to the spill bucket.

## 1. Deploy the connector (console)

Athena console, **Data sources > Create data source > Amazon DynamoDB**:
- Data source name: `ddb`
- Lambda function: **Create Lambda function** opens the Serverless
  Application Repository page for **AthenaDynamoDBConnector**. Set:
  - `AthenaCatalogName` = `riverbend-ddb`
  - `SpillBucket` = the `SpillBucket` output
  - Tick *I acknowledge… custom IAM roles / resource policies*, then **Deploy**.
- Back in Athena, refresh, pick `riverbend-ddb`, then **Create data source**.

The CLI equivalent (`aws serverlessrepo create-cloud-formation-change-set`
followed by `aws athena create-data-catalog`) is in `solve.sh`. SAR names the stack
`serverlessrepo-<name>`.

## 2. Schema inference

DynamoDB is schemaless. The connector samples items to infer column types
(`loyalty_points` becomes `decimal`, `marketing_opt_in` becomes `boolean`). For strict types
you can create a Glue table that carries the property `sourceTable` and a
`classification=dynamodb` parameter, and the connector will use that schema instead.

## 3. Queries

See [`queries.sql`](queries.sql). Notes:
- `"default"` must be quoted because it is a reserved word.
- 4.2 joins a federated table with an S3 table in one statement. Athena pulls
  the DynamoDB rows through the connector and does the join itself.
- The `marketing_opt_in = true`, `region` and `loyalty_tier` filters can be pushed down to the
  connector as a DynamoDB filter expression, but they still use RCUs for a
  full **Scan**. Only a filter on `customer_id` becomes a `Query`/`GetItem`. On a
  large production table, keep federated queries selective, or snapshot the table to S3
  with DynamoDB *Export to S3*.

## 4. Export with CTAS

CTAS writes to S3 through the Glue catalog, so the result becomes an ordinary
lake table that other tools (Glue, Redshift Spectrum, QuickSight) can read
without calling the connector again.

## Clean up

`cleanup.sh` drops the CTAS table, deregisters the `ddb` catalog and deletes the
`serverlessrepo-cq-da-03-ddb-connector` stack (Lambda and IAM role).
