# Data Lakehouse Demonstrated: break-fix challenges

Seven **break-fix challenges**, plus a timed 110-minute mock exam, for practising the skills behind the *AWS Data Lakehouse Demonstrated*
microcredential in **your own AWS account**. The scenario is **Riverbend Outfitters**, an outdoor retailer whose Apache Iceberg lakehouse
on S3 is fed by batch jobs, vendor files and a CDC stream, queried with Athena, and governed with Lake Formation.

Each challenge deploys a deliberately broken environment with Terraform. You diagnose it from the symptoms and fix it.

| Part | Where |
|---|---|
| Handout: situation, how to reproduce, objectives, useful commands, hint ladder | `missions/<Cn-…>/README.md` |
| Broken environment | `missions/<Cn-…>/terraform/` plus the Glue / SQL / Lambda code the challenge is about |
| Self-check (PASS/FAIL) | `missions/<Cn-…>/scenarios/check.py` |
| **Solution, kept separate** | `solutions/<Cn-…>/README.md` (each fault, why it happens, the fix) |
| Reference fix | `solutions/<Cn-…>/fix.patch` (`patch -p1 < …`, undo with `patch -R -p1 < …`) |

## Exam objectives → challenges

| Exam objective | Challenge | You'll work with | Faults |
|---|---|---|---|
| Troubleshoot order ingestion to eliminate duplicate records | [**C1** Orders are counted twice](missions/C1-order-ingestion-duplicates/README.md) | Glue 5.0 Spark job, Iceberg `MERGE INTO`, in-batch dedup with window functions, late and replayed data, `--datalake-formats` | 4 |
| Troubleshoot product catalog schema mismatch and query access patterns | [**C2** The new supplier feed loses data, and catalog queries scan everything](missions/C2-catalog-schema-and-access/README.md) | Iceberg schema evolution (add column, `float`→`double` promotion), silent `MERGE … SET *` data loss, partition evolution, `rewrite_data_files` | 3 |
| Configure the vendor file processing pipeline | [**C3** Vendor files go nowhere](missions/C3-vendor-file-pipeline/README.md) | S3 → **EventBridge** → **Step Functions** (Lambda validate, `glue:startJobRun.sync`, S3 SDK copy/delete, Choice state) → Glue → Iceberg | 4 |
| Optimize analytics query performance to sub-5-second SLA | [**C4** The dashboard is too slow](missions/C4-query-performance-sla/README.md) | 20M-row Iceberg table with ~36,000 small files, `write.target-file-size-bytes`, distribution mode, compaction, snapshot expiry, partition pruning in **Athena** | 4 |
| Configure tag-based access control for data science and intern roles | [**C5** Tag-based access for data science and interns](missions/C5-tag-based-access/README.md) | **Lake Formation** LF-Tags, LF-TBAC grant expressions, column-level tags, registered locations, `IAMAllowedPrincipals` | 4 |
| Configure data cell filters for marketing and regional manager access | [**C6** Row- and column-level access](missions/C6-data-cell-filters/README.md) | Lake Formation **data cell filters** (row filter + column exclusions), grants on filters vs tables | 4 |
| Troubleshoot streaming upsert failures in Amazon Data Firehose delivering to Apache Iceberg tables | [**C7** Streaming upserts into Iceberg are failing](missions/C7-firehose-iceberg-upserts/README.md) | **Firehose** Iceberg destination, `unique_keys`, `append_only`, JQ metadata extraction (operation routing), delivery role, error prefix and logs | 4 |

Services covered: Amazon Athena, Amazon EventBridge, Amazon Data Firehose, AWS Glue (jobs and Data Catalog), AWS Lake Formation,
Amazon S3 and AWS Step Functions (all those listed for the exam), plus Lambda, IAM and CloudWatch Logs.

## Prerequisites

- A sandbox AWS account where you're an administrator. The default Region is **us-west-2** (pass `-var region=…` to every stack to change it).
- Terraform ≥ 1.6, AWS CLI v2, Python 3.10+ with `boto3` ≥ 1.40.
- C5 and C6 make you a **Lake Formation data lake administrator**. The deploy backs up your Data Lake settings to
  `~/.riverbend-lh-lakeformation-settings-backup.json`, and destroying the last of C5/C6 restores them. Both challenges register only
  `s3://<lake>/governed/c5|c6/` and use their own databases, so the other challenges' Glue jobs are unaffected.

## Running

```bash
./scripts/deploy.sh base       # once: raw / lake / scripts / Athena buckets, Glue database riverbend_lakehouse, Athena workgroup, Glue role
./scripts/deploy.sh C1         # any challenge: setup.py -> terraform apply -> post_deploy.py
cat missions/C1-order-ingestion-duplicates/README.md
python3 missions/C1-order-ingestion-duplicates/scenarios/check.py
./scripts/destroy.sh C1
./scripts/destroy.sh base      # when you've finished
```

Glue jobs run Glue 5.0 (Spark 3.5, Iceberg 1.7) through a shared module (`common/terraform/iceberg_glue_job`) with the `glue_catalog`
Iceberg catalog. Athena uses engine v3 in the workgroup `riverbend-lh`. Tables are in `s3://<lake>/warehouse/`.

### Mock exam

```bash
./scripts/exam.sh start            # deploys base + C1..C7, shuffles them, starts a 110-minute clock
cat exam/briefing.md               # each challenge's brief, hints removed
./scripts/exam.sh status           # time left
./scripts/exam.sh grade            # runs every challenge's scenarios/check.py and prints a score
./scripts/exam.sh end              # destroys the challenge stacks (then ./scripts/destroy.sh base)
```

`./scripts/exam.sh start C4,C5,C7` picks your own set. Allow ~15 minutes for the deploy (C4 loads 20M rows once).

## Cost

| Item | Notes |
|---|---|
| Glue jobs (C1–C4) | G.1X × 2 workers (C4: 4), billed per second with a 1-minute minimum. A full C1 run is 3 short jobs, roughly $0.10–0.30. C4's one-off 20M-row load plus compaction is roughly $0.50–1 |
| Athena | $5 per TB scanned. Every challenge scans megabytes to a few GB: cents |
| Firehose (C7) | Per GB ingested (a few hundred KB here), plus the Iceberg-destination charge: cents |
| Step Functions, Lambda, EventBridge, Lake Formation | Free tier / pennies |
| S3 | Small. The Athena results bucket expires objects after 7 days. `destroy.sh base` force-empties all buckets |

## What has (and hasn't) been tested

Nothing in this kit has been deployed to AWS by its author.
- **Terraform:** all of it passes `terraform validate` against the AWS provider (6.72).
- **Glue scripts:** run locally with Spark 3.5 + Iceberg against a local warehouse, covering the C1 dedup/merge faults and fix, the C2 silent
  data loss and schema/partition evolution, and the C4 small-file layout, compaction and query results (at reduced scale).
- **Lambda and data:** the C3 validator and the data generators were run locally.
- **Patches:** every solution patch applies.
- **Untested service-side behaviour:** Lake Formation evaluation (C5/C6), Firehose Iceberg delivery and JQ routing (C7), Step Functions
  execution (C3), exact Athena timings for the C4 SLA, and exact AWS error texts. Expect small adjustments on the first real deployment
  of each challenge.

These challenges are original practice material for self-study. They aren't affiliated with AWS or with any official assessment.
