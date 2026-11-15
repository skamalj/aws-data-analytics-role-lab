# Challenge C3 solution: Vendor files go nowhere

```bash
patch -p1 < solutions/C3-vendor-file-pipeline/fix.patch
./scripts/deploy.sh C3
aws s3 rm s3://<raw bucket>/vendors/ --recursive          # clean slate
python3 missions/C3-vendor-file-pipeline/scenarios/drop_vendor_files.py
python3 missions/C3-vendor-file-pipeline/scenarios/check.py
```

| # | Fault | Symptom | Fix |
|---|---|---|---|
| 1 | `aws_s3_bucket_notification … eventbridge = false` | No executions at all, and the rule's metrics show no matches | `eventbridge = true`. S3 publishes events to EventBridge only when this bucket setting is on |
| 2 | Rule prefix `vendor/incoming/` ≠ actual `vendors/incoming/` | Still no executions | `prefix = "vendors/incoming/"`. This also matters for correctness: the pipeline itself writes to `vendors/processed/` and `vendors/quarantine/`, and a rule matching `vendors/` would re-trigger on its own copies (a loop) |
| 3 | Choice: `StringEquals = "true"` on a JSON **boolean** | Every file, valid or not, is quarantined | `BooleanEquals = true`. Choice rules are type-strict |
| 4 | The Load task passes `--input_key`, but the job requires `--source_key` | Valid files reach Load, then the Glue run fails: *the following arguments are required: --source_key* | Pass `"--source_key.$" = "$.detail.object.key"`. Glue job arguments must match `getResolvedOptions` exactly, including the leading `--` |

Why the design works:
- The `.sync` Glue integration means Step Functions waits for the job and fails the execution if it fails.
- S3 SDK integrations (`copyObject` + `deleteObject`) archive files without Lambda.
- Validation before loading keeps bad files out of the Iceberg table entirely.
- `MERGE` on `shipment_id` makes re-delivered files harmless.
