# Lab 10: Real-Time Data Processing

## Scenario

Riverbend stores frozen meals in three cold-storage warehouses. Ten
freezers stream telemetry every second. Last month a door was left open
overnight and €40k of stock was lost, because the hourly batch report noticed too late.

Operations wants:
- a **live dashboard** of freezer temperatures
- an **alert within about a minute** when a freezer's *average* temperature over a minute rises above **−15 °C**
- a pipeline that **never stalls** on a bad sensor message. Broken records must be kept for investigation

## What the starting environment gives you

`./scripts/deploy.sh 10-real-time-data-processing` creates (OpenSearch takes ~15–20 minutes):

| Resource | Notes |
|---|---|
| Kinesis stream `riverbend-freezer-telemetry` | 1 shard. Fed by a scheduled **producer Lambda** with 10 readings/s. Every 10 minutes one freezer (in rotation) has its door open for 3 minutes. Every 5 minutes one **malformed** record arrives |
| OpenSearch Service domain `cq-da-10-ops` | 1 × t3.small.search, fine-grained access control. Master user `admin`, password in Secrets Manager (`OpenSearchSecretArn`) |
| SQS queue `cq-da-10-failed-records` | For records and batches that can't be processed |
| IAM role `cq-da-10-processor-role` | For **your** Lambda: read the stream, send to SQS, `es:ESHttp*` on the domain |

Reading example:

```json
{"device_id":"freezer-04","warehouse":"WH-2","reading_ts":"2026-11-11T10:15:02.123Z",
 "temperature_c":-17.82,"humidity_pct":41.3,"door_open":false}
```

Pause the producer with `./scripts/deploy.sh 10-real-time-data-processing ProducerEnabled=false`.

## Your tasks

1. Open **OpenSearch Dashboards** (output `OpenSearchDashboardsUrl`) and log in as the master user.
2. **Authorise your Lambda.** In the security plugin, create a role `freezer_writer` that can only
   write `freezer-*` indices, and map it to the IAM role `cq-da-10-processor-role`.
3. Create an **index template** for `freezer-*` so timestamps are `date`, IDs are
   `keyword` and temperatures are `float`.
4. **Write the processor Lambda** `cq-da-10-freezer-processor` (use the provided role):
   - index every reading into a daily index `freezer-readings-YYYY.MM.DD`, signing requests with SigV4
   - use **60-second tumbling windows** to compute, per device and window, the count, average, max and door-open readings.
     Write them to `freezer-window-stats`, and also write an alert document to `freezer-alerts` when the average is above −15 °C
   - send malformed records to the SQS queue, and **don't** fail the invocation
   - make re-processing safe: retries must not create duplicate documents
5. **Connect it to the stream** with an event source mapping: start at `LATEST`, 60-second tumbling window,
   split batches on error, at most 3 retries, and failed-batch information sent to the SQS queue.
6. Build a **Freezer operations** dashboard: a temperature line per device, plus an alerts table.
7. Questions:
   1. What happens to the shard if your function throws an exception on the malformed record, and you have no retry limit?
   2. Why alert on the window average instead of individual readings?
   3. When would you choose Amazon Managed Service for Apache Flink over this design?

## How you know you're done

Behaviour matches [`expected-results.md`](../../solutions/10-real-time-data-processing/expected-results.md):
about 3 alerts per 10 minutes for one rotating freezer, about 1 SQS message per 5 minutes, and no Lambda errors.

## Hints

<details><summary>Signing requests to OpenSearch from Lambda without extra libraries</summary><code>botocore.auth.SigV4Auth</code> + <code>botocore.awsrequest.AWSRequest</code> for service <code>es</code>, then send with <code>urllib</code>.</details>
<details><summary>Tumbling windows</summary>Return <code>{"state": {...}}</code> from each invocation. The next invocation for the same window receives it in <code>event["state"]</code>. <code>event["isFinalInvokeForWindow"]</code> tells you when to emit results.</details>
<details><summary>403 from OpenSearch</summary>With fine-grained access control, the IAM role must be mapped as a <b>backend role</b> to an OpenSearch role.</details>

## Cleanup

```bash
./solutions/10-real-time-data-processing/cleanup.sh
./scripts/destroy.sh 10-real-time-data-processing
```

**Cost:** about $1/day for OpenSearch, plus about $0.5/day for the shard and producer. Destroy the stack when you've finished.
