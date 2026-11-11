# Lab 09: check values

Streaming data is random, so check **shapes and ratios**, not exact numbers.

| Check | Expected |
|---|---|
| Records on the stream | JSON like `{"event_id": "...", "event_type": "page_view", "session_id": "sess-123", ...}` |
| S3 layout | `events/event_type=<type>/dt=YYYY-MM-DD/hour=HH/riverbend-clickstream-to-s3-...gz` |
| First objects in S3 | about 60–90 seconds after the stream exists (the 60-second buffer interval) |
| Event mix | page_view ≈ 70%, add_to_cart ≈ 15%, search ≈ 10%, checkout ≈ 5% (±2 points after a few minutes) |
| Cart-to-checkout conversion | ≈ 33% in every region |
| Events per minute at RATE=20 | ≈ 1,200 |
| During the 1,500/s burst on 1 shard | `WriteProvisionedThroughputExceeded` > 0 and the producer logs `throttled=` rising (`journalctl -u clickstream-producer`) |
| After resharding to 2 shards | throttling stops. `aws kinesis describe-stream-summary` shows `OpenShardCount: 2` |
| `errors/` prefix | empty. If not, read the error records: a malformed record or a JQ failure |
