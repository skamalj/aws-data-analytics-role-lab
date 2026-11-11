# AWS Data Analytics Role Labs (self-hosted)

> Also in this repo: [**Agentic AI Demonstrated: break-fix missions**](agentic-ai-demonstrated/README.md), six Terraform
> missions on Amazon Bedrock AgentCore (identity, gateway/MCP, knowledge bases, memory, private networking, guardrails).
>
> And: [**Databases for Agentic AI: break-fix missions**](databases-for-agentic-ai/README.md), five missions on Aurora
> PostgreSQL/pgvector, DynamoDB checkpoints (`langgraph-dynamodb-checkpoint`), MCP diagnostics and agent data routing.

Twelve hands-on labs modelled on the **AWS Cloud Quest: Data Analytics** role, built to run in
**your own AWS account**. Each lab has three parts:

| Part | Where | What |
|---|---|---|
| **Starting environment** | `labs/<lab>/infra/` | CloudFormation template + a seed script that loads synthetic data, plus scenario drivers (scripts that "make things happen") |
| **Problem** | `labs/<lab>/README.md` | Scenario, what you're given, tasks, hints, acceptance checks |
| **Solution** | `solutions/<lab>/` | Walkthrough (console + reasoning), `solve.sh` (automated reference), `cleanup.sh`, `expected-results.md` |

All labs share one fictional retailer, **Riverbend Outfitters**, and one deterministic
data generator ([`common/datagen.py`](common/datagen.py)). That means `expected-results.md` can give
exact numbers to check your answers against.

## Labs

| # | Lab | You build | Main services |
|---|---|---|---|
| 01 | [Data Lakes](labs/01-data-lakes/README.md) | Glue crawler + catalog over raw exports, Athena SQL | S3, Glue, Athena, IAM |
| 02 | [Querying the Data Lake](labs/02-querying-the-data-lake/README.md) | Partitioned Parquet via CTAS, views, workgroup data limits | Athena, Glue, S3 |
| 03 | [Federated Queries](labs/03-federated-queries/README.md) | Athena DynamoDB connector, joins across DynamoDB and S3, CTAS export | Athena, DynamoDB, Lambda, S3 |
| 04 | [Populating the Data Catalog](labs/04-populating-the-data-catalog/README.md) | Crawlers with classifiers and exclusions, partition projection, incremental crawls | Glue, Athena, S3 |
| 05 | [Event-Driven Serverless ETL](labs/05-event-driven-serverless-etl/README.md) | S3 → EventBridge → Lambda → Glue Spark job, quarantine, alerts | S3, Lambda, Glue, EventBridge, SNS |
| 06 | [Securing the Data Lake](labs/06-securing-the-data-lake/README.md) | Column-, row- and cell-level access with Lake Formation | Lake Formation, IAM, Glue, Athena |
| 07 | [Cloud Data Warehouse](labs/07-cloud-data-warehouse/README.md) | Star schema, COPY, Spectrum, materialized views, usage limits | Redshift Serverless, S3, Glue |
| 08 | [Daily Batch Extraction](labs/08-daily-batch-extraction/README.md) | Incremental JDBC extraction from a private database, orchestrated and scheduled | RDS (Aurora PostgreSQL), VPC, Glue, Step Functions, EventBridge Scheduler, SNS |
| 09 | [Streaming Ingestion](labs/09-streaming-ingestion/README.md) | Kinesis stream + Firehose with dynamic partitioning, a spike test | EC2, Kinesis Data Streams, Firehose, S3, Athena |
| 10 | [Real-Time Data Processing](labs/10-real-time-data-processing/README.md) | Lambda tumbling-window analytics, alerting, live dashboard, dead-lettering | Kinesis, Lambda, OpenSearch Service, SQS |
| 11 | [Big Data Processing](labs/11-big-data-processing-emr/README.md) | Spark sessionization, registered in the Glue catalog | EMR (Serverless), S3, Glue, Athena |
| 12 | [Business Intelligence](labs/12-business-intelligence-quicksight/README.md) | SPICE dataset, dashboard, row-level security, refresh schedule | QuickSight, Athena, Glue |

### Service coverage

| Service | Labs |
|---|---|
| Amazon Athena | 01, 02, 03, 04, 05, 06, 08, 09, 11, 12 |
| Amazon DynamoDB | 03 |
| Amazon EC2 | 09 (producer instance, SSM Session Manager) |
| Amazon EMR | 11 |
| AWS Glue | 01, 02, 04, 05, 07, 08, 11, 12 |
| AWS IAM | every lab (least-privilege roles); 06 in depth |
| Amazon Kinesis (Data Streams, Firehose) | 09, 10 |
| AWS Lake Formation | 06 |
| AWS Lambda | 03, 05, 10 |
| Amazon OpenSearch Service | 10 |
| Amazon QuickSight | 12 |
| Amazon RDS (Aurora PostgreSQL) | 08 |
| Amazon Redshift | 07 |
| Amazon S3 | every lab |
| Amazon SQS | 10 |
| AWS Step Functions | 08 |
| Amazon VPC | 08 (private subnets, endpoints, security groups), 09 |

## Prerequisites

- An AWS account you're allowed to experiment in, with administrator access. **Don't use production.**
- AWS CLI v2 configured with a default region, Python 3.9+ with `boto3`, `bash` and `zip`.
  **AWS CloudShell** has all of these, so the easiest way to start is to clone this repo in CloudShell.
- Lab 12 needs a QuickSight subscription (see that lab).

## Running a lab

```bash
./scripts/deploy.sh 01-data-lakes          # create the starting environment and seed data
cat labs/01-data-lakes/README.md           # read the problem, then solve it
./solutions/01-data-lakes/solve.sh         # (optional) reference solution, end to end
./solutions/01-data-lakes/cleanup.sh       # remove what you / the solution built
./scripts/destroy.sh 01-data-lakes         # remove the starting environment
```

Stacks are named `cq-da-NN`. Every resource is tagged `Project=cloud-quest-data-analytics`.
Labs are independent of each other, so you can do them in any order. Deploy only the lab you're working on.

## Cost

Set up an AWS Budget with an alert before you start. Most labs cost cents. These bill while they exist:

| Lab | Billed while running | Rough cost |
|---|---|---|
| 07 | Redshift Serverless (only while queries run) + storage | ~$3 per hour of active querying at 8 RPU |
| 08 | Aurora Serverless v2 (0.5 ACU minimum) + 2 interface endpoints | ~$2–3/day |
| 09 | 1 Kinesis shard + t3.micro + Firehose | ~$0.5/day |
| 10 | OpenSearch t3.small + 1 shard + producer Lambda | ~$1.5/day |
| 12 | QuickSight subscription | per user per month after the trial |

Always run the lab's `cleanup.sh` and then `scripts/destroy.sh` when you've finished.

## Repository layout

```
common/      datagen.py (synthetic data), awslab.py (stack outputs, seeding, bucket emptying),
             athena_run.py / redshift_run.py (run SQL files from the CLI), lib.sh (bash helpers)
scripts/     deploy.sh, destroy.sh
labs/NN-*/   README.md (problem) + infra/ (template.yaml, seed.py, scenario drivers)
solutions/NN-*/  README.md (walkthrough), solve.sh, cleanup.sh, expected-results.md, code/SQL
```

These labs are an independent, self-hosted study aid inspired by the topics of the
Cloud Quest Data Analytics role. They aren't affiliated with or endorsed by AWS, and they don't
reproduce Cloud Quest content.
