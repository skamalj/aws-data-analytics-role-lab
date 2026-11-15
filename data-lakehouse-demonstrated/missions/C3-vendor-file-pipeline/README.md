# Challenge C3: Vendor files go nowhere

**Exam objective:** *Configure the vendor file processing pipeline*
**Services:** Amazon S3 event notifications, Amazon EventBridge, AWS Step Functions (Lambda, Glue `.sync` and S3 SDK integrations), AWS Lambda, AWS Glue, Apache Iceberg
**Time:** 30–40 minutes  |  **Deploy:** `./scripts/deploy.sh C3`

## Situation

Three logistics vendors upload a daily shipment CSV to `s3://<raw bucket>/vendors/incoming/`. Each upload must be processed automatically:

```
S3 Object Created ─► EventBridge rule riverbend-lh-c3-vendor-file-arrived ─► Step Functions riverbend-lh-c3-vendor-files
   Validate (Lambda: required columns, numeric quantities)
     ├─ valid   ─► Load (Glue job riverbend-lh-c3-vendor-load: MERGE into Iceberg vendor_shipments) ─► copy to vendors/processed/
     └─ invalid ─► copy to vendors/quarantine/
   ─► delete the file from vendors/incoming/
```

All of it is in [`terraform/main.tf`](terraform/main.tf), plus the Lambda [`lambdas/validate.py`](lambdas/validate.py) and the job [`glue/vendor_load.py`](glue/vendor_load.py).
The team says it "deployed fine", but no vendor file has ever been processed.

## Run it

```bash
python3 missions/C3-vendor-file-pipeline/scenarios/drop_vendor_files.py   # 2 valid files + 1 missing the quantity column
python3 missions/C3-vendor-file-pipeline/scenarios/check.py
```

Before re-running `drop_vendor_files.py`, move or delete any files left in `vendors/incoming/`, `processed/` and `quarantine/`, so that
the check sees one clean run.

## Objectives

1. Every upload to `vendors/incoming/` starts **one** pipeline execution, and nothing else does.
2. Valid files are loaded into `riverbend_lakehouse.vendor_shipments` and archived in `vendors/processed/`.
3. Invalid files are **not** loaded, and end up in `vendors/quarantine/`.
4. All executions end `SUCCEEDED`, and `vendors/incoming/` is empty afterwards.

## Done when

`check.py` reports 6/6 checks passed (300 shipments from 2 files).

## Useful commands

```bash
aws s3api get-bucket-notification-configuration --bucket <raw bucket>
aws events describe-rule --name riverbend-lh-c3-vendor-file-arrived --query EventPattern --output text
aws stepfunctions list-executions --state-machine-arn <arn> --max-items 5
aws stepfunctions get-execution-history --execution-arn <arn> --reverse-order --max-items 5
aws glue get-job-runs --job-name riverbend-lh-c3-vendor-load --max-items 2 --query 'JobRuns[].ErrorMessage'
```

<details><summary>Hint 1</summary>An EventBridge rule can only match events that actually reach EventBridge. Where does S3 decide whether to send them? Then compare the rule's pattern with the real object keys.</details>
<details><summary>Hint 2</summary>In the execution history, look at the input and output of the <code>IsValid</code> Choice state. What type is <code>valid</code>, and what does the rule compare it with?</details>
<details><summary>Hint 3</summary>Compare the arguments the state machine passes to the Glue job with the arguments the job script requires.</details>
