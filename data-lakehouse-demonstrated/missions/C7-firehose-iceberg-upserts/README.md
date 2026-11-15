# Challenge C7: Streaming upserts into Iceberg are failing

**Exam objective:** *Troubleshoot streaming upsert failures in Amazon Data Firehose delivering to Apache Iceberg tables*
**Services:** Amazon Data Firehose (Iceberg destination, metadata extraction / JQ routing), Apache Iceberg, AWS Glue Data Catalog, IAM, Amazon Athena, CloudWatch Logs
**Time:** 30–40 minutes  |  **Deploy:** `./scripts/deploy.sh C7` (creates the Iceberg table `riverbend_lakehouse.order_status` first)

## Situation

The order service publishes a change event every time an order changes:

```json
{"order_id": "O-70001", "status": "SHIPPED", "amount": 189.0, "updated_at": "2026-03-10T12:00:00Z", "op": "update"}
{"order_id": "O-70190", "op": "delete"}
```

`op` is `insert`, `update` or `delete`. Firehose stream `riverbend-lh-c7-order-status` (Direct PUT) must keep `order_status` as **one row per
order holding its latest state**, so that customer service can query it in Athena. Today nothing arrives at first. Once it does, the
table fills with duplicate rows and orders that should have been deleted.

Everything is in [`terraform/main.tf`](terraform/main.tf).

## Reproduce and check

```bash
python3 missions/C7-firehose-iceberg-upserts/scenarios/stream_orders.py   # resets the table, then replays 3 waves (~6 minutes)
python3 missions/C7-firehose-iceberg-upserts/scenarios/check.py
```

Where to look: CloudWatch Logs `/aws/kinesisfirehose/riverbend-lh-c7-order-status` (stream `DestinationDelivery`), the error objects in
`s3://<lake>/firehose-errors/c7/` (each one has an `errorCode` and `errorMessage`), and Firehose **Monitoring** in the console.

```sql
SELECT order_id, count(*) FROM riverbend_lakehouse.order_status GROUP BY 1 HAVING count(*) > 1;
SELECT * FROM riverbend_lakehouse."order_status$snapshots";
```

## Done when

`check.py` reports 6/6: no error objects, 180 orders with one row each and their latest status, and the 20 purged orders gone.

<details><summary>Hint 1</summary>The first failure is about permissions. Committing to an Iceberg table means writing new metadata <b>and</b> pointing the catalog at it.</details>
<details><summary>Hint 2</summary>Two settings on the stream decide whether Firehose can do anything other than append, and which columns identify "the same row".</details>
<details><summary>Hint 3</summary>The JQ metadata-extraction query tells Firehose the operation for each record. Compare its field name with the producer's.</details>
