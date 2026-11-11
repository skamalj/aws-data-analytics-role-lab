# Lab 09: Streaming Ingestion

## Scenario

Riverbend's website and mobile apps emit clickstream events (page views,
searches, add-to-cart, checkout). An EC2-hosted collector already formats
them, but it has nowhere to send them. Marketing wants the raw events in the data lake **within
about a minute**, organised so they can query one event type cheaply. The platform
team needs to know what happens when traffic spikes during a sale.

## What the starting environment gives you

`./scripts/deploy.sh 09-streaming-ingestion` creates:

| Resource | Notes |
|---|---|
| VPC + public subnet + EC2 instance `cq-da-09-clickstream-producer` | Runs the systemd service `clickstream-producer`. It **waits** until a Kinesis stream called `riverbend-clickstream` exists, then sends 20 events/s. No SSH: use **SSM Session Manager**. Config is in `/etc/clickstream-producer.env` (`RATE=`) |
| Instance role | May `PutRecords` to `riverbend-clickstream` only |
| `RawEventsBucket` | Destination for raw events |
| IAM role `cq-da-09-firehose-role` | May read `riverbend-clickstream` and write the bucket |
| Glue database `riverbend_stream`, Athena workgroup `cq-da-09` | |

Event example:

```json
{"event_id":"8c1f...","event_ts":"2026-11-11T10:15:02.123Z","event_type":"add_to_cart",
 "customer_id":"C00042","session_id":"sess-981","product_id":"P104","device":"ios",
 "region":"EU","price":159}
```

## Your tasks

1. **Create the Kinesis data stream** `riverbend-clickstream`, provisioned mode, 1 shard.
2. **Prove data is flowing**: read a few records from the stream (console data viewer or CLI).
   On the instance, `journalctl -u clickstream-producer` shows the producer's progress.
3. **Create a Firehose stream** `riverbend-clickstream-to-s3` that reads from the stream and writes to the bucket:
   - path `events/event_type=<event_type>/dt=<yyyy-MM-dd>/hour=<HH>/`, where `event_type` comes **from inside each record**
   - failed records go to `errors/`
   - GZIP, buffered for at most 60 seconds
   - use the provided Firehose role
4. **Query it.** Create an Athena table `riverbend_stream.clickstream` whose
   partitions don't need a crawler or `MSCK REPAIR`. Then report:
   - the event mix for today (count and %)
   - cart-to-checkout conversion and checkout value per region
   - how far behind real time the data in S3 is
5. **Spike test.** Change the producer to `RATE=1500` and restart it. Find
   the evidence of throttling (CloudWatch metric and producer log). Fix it without
   stopping the producer, confirm the throttling stops, then set `RATE=20` again.
6. Question: the producer only *counts* throttled records. What happens to
   them, and what should a production producer do?

## How you know you're done

See [`expected-results.md`](../../solutions/09-streaming-ingestion/expected-results.md). The data is random, so it lists ratios and behaviours rather than exact numbers.

## Hints

<details><summary>Partitioning by a field inside the record</summary>Firehose <b>dynamic partitioning</b> with inline JSON parsing (JQ). Then use <code>!{partitionKeyFromQuery:event_type}</code> in the prefix.</details>
<details><summary>Shard limits</summary>Per shard: 1,000 records/s or 1 MiB/s written, and 2 MiB/s read. Look at <code>UpdateShardCount</code>, or on-demand mode.</details>

## DIY challenge

- Add Firehose **record format conversion** to Parquet using a Glue table schema.
- Add a Lambda transformation in Firehose that drops `page_view` events from bots (for example, every event with `device = "desktop"` and region `APAC`, as a stand-in rule).

## Cleanup

```bash
./solutions/09-streaming-ingestion/cleanup.sh
./scripts/destroy.sh 09-streaming-ingestion
```

**Cost:** about $0.02/h for the shard + t3.micro, plus Firehose at $0.029/GB
(and dynamic partitioning per GB and per object). Stopping the stream also
stops the producer's writes. Destroy the stack when you've finished.
