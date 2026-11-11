# Lab 10: check values

The producer sends 10 readings per second (one per freezer), with a few-second gap between its one-minute invocations.

| Check | Expected after ~10 minutes |
|---|---|
| `freezer-readings-*` | ≈ 550–600 docs per minute. Re-processing a batch must **not** raise the count (doc ids are idempotent) |
| `freezer-window-stats` | 10 docs per minute (one per freezer per 60-second window) |
| `freezer-alerts` | ≈ **3 per 10 minutes**, all for **one** freezer at a time, rotating through freezer-01 to freezer-10 every 10 minutes. Averages ≈ −14, −10 and −6 °C |
| SQS `cq-da-10-failed-records` | ≈ **1 message per 5 minutes**, body `{"reason": "...", "data": "freezer-03;-17.9;THIS IS NOT JSON", ...}` |
| Lambda `IteratorAge` metric | stays below a few seconds |
| Lambda errors | 0. The malformed records must not cause function errors or retries |

If alerts fire for many freezers every minute, your threshold uses individual readings (spiky) instead of the window average.
