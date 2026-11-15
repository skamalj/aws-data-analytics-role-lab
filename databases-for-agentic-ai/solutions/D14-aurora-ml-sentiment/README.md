# Mission D14 solution: How do customers feel about this product?

```bash
patch -p1 < solutions/D14-aurora-ml-sentiment/fix.patch
./scripts/deploy.sh D14       # association + policy, then post_deploy runs refresh_sentiment.sql
python3 missions/D14-aurora-ml-sentiment/scenarios/check.py
```

## Fault 1: the `aws_ml` extension isn't installed

| | |
|---|---|
| Symptom | `function aws_comprehend.detect_sentiment(…) does not exist` / `schema "aws_comprehend" does not exist` |
| Fix | `CREATE EXTENSION IF NOT EXISTS aws_ml CASCADE` (as the admin user, which is an `rds_superuser` member). It installs `aws_comprehend`, `aws_sagemaker` and `aws_bedrock` (depending on version) |

## Fault 2: the role is associated for the wrong feature, with the wrong permission

| | |
|---|---|
| Symptom | Comprehend calls fail with an error saying no IAM role is configured for Comprehend, or with an AccessDenied from Comprehend |
| Root cause | Aurora picks the role **by feature name**. The association said `SageMaker`. The role's policy only allowed `comprehend:DetectDominantLanguage` |
| Fix | `feature_name = "Comprehend"`, and allow `comprehend:DetectSentiment` + `comprehend:BatchDetectSentiment` (the extension batches rows). Comprehend doesn't support resource-level permissions for these actions, hence `Resource: "*"` |

## Fault 3: ML on every question, through the agent identity

| | |
|---|---|
| Symptom | `permission denied for schema commerce`. If access were granted, every question would score every review again: slow and billed each time |
| Fix | The refresh job scores **unscored** reviews once (`UPDATE … WHERE sentiment IS NULL`) and stores `sentiment`/`sentiment_confidence`. The agent reads `reporting.product_review_sentiment` (aggregates only), and `trail_desk_app` gets `SELECT` on that view and nothing else |

Expected for P101: 33 reviews, split roughly 3:1:1 positive / neutral / negative (the templates are worded so Comprehend classifies them clearly).

## Debrief answers

1. Reviews don't change, so scoring is a one-time cost per review. Per-question scoring multiplies cost and latency by the number of questions. On demand is fine for
   one-off analyses of small sets, or for text that's new every time (for example, the customer's own message).
2. Pros: no data movement, plain SQL, transactional with the data, simple to operate. Cons: ML calls compete with database capacity and connections,
   batch sizes and throttling are tied to the database, and there's less control over retries and observability than in a dedicated pipeline.
3. A trigger or periodic job: a scheduled `UPDATE … WHERE sentiment IS NULL` (EventBridge Scheduler → Lambda → Data API), or a CDC stream into a Lambda that scores and writes back.
4. `aws_bedrock` functions to summarise reviews or extract themes and embeddings in SQL (then pgvector similarity on them), and `aws_sagemaker` for a
   custom model (for example, churn risk from orders).
