# Lab 10 solution: Real-Time Data Processing

Files: [`processor/app.py`](processor/app.py) (the Lambda), [`setup_opensearch.py`](setup_opensearch.py)
(security role mapping, index template, Dashboards index patterns), [`check.py`](check.py), `solve.sh`.

## Architecture

```
producer Lambda (every minute, 10 readings/s) ─► Kinesis riverbend-freezer-telemetry (1 shard)
                                                      │ event source mapping
                                                      │   tumbling window 60 s, batch 1000, bisect on error,
                                                      │   3 retries, on-failure ─► SQS
                                                      ▼
                                       Lambda cq-da-10-freezer-processor
                    ┌─────────────── every invocation ───────────────┬──────────────── malformed ──────────┐
                    ▼                                                 ▼                                      ▼
   OpenSearch freezer-readings-YYYY.MM.DD (SigV4)      state carried to next invocation        SQS cq-da-10-failed-records
                    └──── final invocation of each window ──► freezer-window-stats, freezer-alerts (avg > −15 °C)
                                                      ▼
                                         OpenSearch Dashboards (line chart + alert table)
```

## Why each setting

| Setting | Why |
|---|---|
| **Tumbling window 60 s** | Lambda keeps per-window state (`event["state"]`) for you. You get "average per device per minute" with no database. State is limited to 1 MB per shard |
| Alert on the **window average** | Single readings are noisy (σ = 0.5 °C). An average over 60 readings above −15 °C is a real door-open event |
| Idempotent `_id` (device + timestamp / window start) | Kinesis + Lambda is **at-least-once**. A retried batch overwrites the same documents |
| Malformed records → SQS **by code** | A poison record must never fail the batch. If it did, the shard would stall and retry until the record expires |
| `BisectBatchOnFunctionError` + `MaximumRetryAttempts 3` + **on-failure destination SQS** | For real failures (for example OpenSearch down), Lambda halves the batch to isolate bad records, gives up after 3 retries and sends the batch's **metadata** (shard, sequence range) to SQS, so you can replay it from the stream later |
| FGAC role `freezer_writer` mapped to the Lambda's **IAM role ARN** | With fine-grained access control, IAM signing gets the request *in*, and the OpenSearch security plugin decides what it may do. Least privilege: write to `freezer-*` only |

## OpenSearch Dashboards (task 6)

Log in at the `OpenSearchDashboardsUrl` output. The user is `admin`, and the password is in the
`cq-da-10-opensearch-admin` secret.
1. **Discover**: index pattern `freezer-readings-*`, last 15 minutes.
2. **Visualize > Create > Line**: Y = average `temperature_c`, X = date histogram on
   `reading_ts` (1 minute), split series by terms `device_id`. One line climbs every 10 minutes.
3. **Visualize > Data table** on `freezer-alerts`: columns `device_id`, `window_start`, `avg_temp_c`.
4. Put both on a dashboard called **Freezer operations**, auto-refreshing every 30 seconds.
5. DIY: **Alerting** plugin, with a monitor on `freezer-alerts` that sends to an SNS channel.

## Alternatives worth knowing

- **Amazon Managed Service for Apache Flink** for stateful stream processing: event-time windows, joins between
  streams and exactly-once state. Use it when the logic outgrows Lambda's 1 MB window state or 15-minute limit.
- **Firehose → OpenSearch** if you only need to index raw events, with no per-window logic.
- **OpenSearch Ingestion (OSIS)** pipelines read from Kinesis directly.
