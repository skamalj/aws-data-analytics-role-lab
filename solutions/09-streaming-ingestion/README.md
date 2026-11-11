# Lab 09 solution: Streaming Ingestion

Files: [`template.yaml`](template.yaml) (stream + Firehose), [`queries.sql`](queries.sql), `solve.sh`.

## Architecture

```
EC2 producer (systemd, PutRecords, partition key = session_id)
        │  HTTPS via the internet gateway (could also be a Kinesis interface endpoint)
        ▼
Kinesis Data Stream riverbend-clickstream  (1 shard → 2 shards, 24 h retention, KMS)
        │  Firehose polls the stream as its source
        ▼
Amazon Data Firehose riverbend-clickstream-to-s3
   ├─ MetadataExtraction (JQ): partition key event_type
   ├─ buffer 60 s / 64 MB, GZIP
   ├─ s3://events/events/event_type=…/dt=…/hour=…/
   └─ failures → s3://events/errors/<error-type>/dt=…/
        ▼
Athena table riverbend_stream.clickstream (partition projection: enum × date × integer)
```

## Key decisions

| Decision | Reasoning |
|---|---|
| Kinesis Data Streams in front of Firehose | Lets you add more consumers later (for example a Lambda consumer, as in Lab 10), replay 24 hours of data, and control ordering per partition key. Writing directly to a Firehose `DirectPut` stream is simpler if S3 is the only destination |
| Partition key `session_id` | High cardinality spreads records across shards evenly. Events for one session stay ordered on one shard |
| Provisioned, 1 shard | 1 shard takes **1,000 records/s or 1 MB/s** of writes. At 20 events/s you pay $0.015/h. **On-demand** removes capacity planning, at a higher base price |
| Dynamic partitioning on `event_type` | Analysts usually query one event type. Athena then reads only that prefix. Pick low-cardinality keys only: Firehose limits the number of active partitions |
| Time prefix from `!{timestamp:…}` | This is the **arrival** time at Firehose, not `event_ts`. Late events go into the hour they arrived. To partition by event time, extract it with JQ as a second key |
| Partition projection | New hours and days are queryable immediately, with no crawler |

## The burst (task 5)

At 1,500 records/s one shard rejects about a third of each `PutRecords` batch with
`ProvisionedThroughputExceededException`. `PutRecords` doesn't fail as a whole. It
returns `FailedRecordCount`, and **producers must retry the failed entries**. This
producer only counts them, so data is lost. That's a deliberate "bug" to discuss.
`UpdateShardCount` to 2 (uniform scaling) splits the hash range. Each shard can
receive up to 1,000 records/s, so 1,500/s fits once it's done. You can also switch
the stream to **on-demand** with `update-stream-mode`.

## Console path

1. Kinesis, **Create data stream** `riverbend-clickstream`, Provisioned, 1 shard.
2. Within 30 seconds the producer starts. Check **Monitoring > Incoming data**, or use the **Data viewer** tab.
3. Amazon Data Firehose, **Create Firehose stream**: source *Kinesis Data Streams*, destination *S3*.
   Turn on **Dynamic partitioning** and **Inline parsing for JSON**, key `event_type` = `.event_type`.
   Use the prefixes above, buffer 60 s, GZIP, and the *existing* role `cq-da-09-firehose-role`.
4. Run the Athena DDL in `queries.sql`.
5. Session Manager into the instance: `sudo sed -i 's/^RATE=.*/RATE=1500/' /etc/clickstream-producer.env && sudo systemctl restart clickstream-producer`.
