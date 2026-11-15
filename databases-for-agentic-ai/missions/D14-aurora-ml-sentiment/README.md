# Mission D14: How do customers feel about this product?

**Based on:** the sentiment-analysis use case in *Leverage pgvector and Amazon Aurora PostgreSQL for NLP, chatbots and sentiment analysis* (AWS Database Blog): **Aurora machine learning** calling **Amazon Comprehend** from SQL
**Skills:** the `aws_ml` extension, cluster IAM role associations per feature, Comprehend permissions, materialising ML results instead of calling ML per question, curated views for agents
**Time:** 40 minutes  |  **Needs:** `./scripts/deploy.sh base`, then `./scripts/deploy.sh D14`
**Note:** Aurora machine learning exists only on Aurora, so this mission can't be reproduced on a laptop PostgreSQL. Comprehend costs well under $1 for 600 reviews.

## Situation

The "customer intelligence" side of Trail Desk should answer questions like *"How do customers feel about the Trailhead
2P Tent (P101)?"* from the 600 reviews in `commerce.reviews`. Rather than exporting reviews to a separate ML pipeline, the team
uses **Aurora machine learning**: `aws_comprehend.detect_sentiment(text, 'en')` calls Amazon Comprehend **from SQL**.

```
review_insights tool (Lambda, trail_desk_app) ──Data API──► Aurora ──(aws_ml, cluster IAM role)──► Amazon Comprehend
```

- Terraform ([`terraform/main.tf`](terraform/main.tf)) creates the IAM role Aurora uses for Comprehend and associates it with the shared cluster.
- [`db/refresh_sentiment.sql`](db/refresh_sentiment.sql) is the data team's refresh job, run by `post_deploy.py`. It hasn't been written yet.
- [`lambdas/review_insights.py`](lambdas/review_insights.py) is the agent's tool.

## Symptoms

```bash
python3 missions/D14-aurora-ml-sentiment/scenarios/check.py
aws lambda invoke --function-name riverbend-d14-review-insights --payload '{"product_id":"P101"}' --cli-binary-format raw-in-base64-out /dev/stdout
```

## Objectives

1. SQL in the cluster can call Comprehend (`SELECT … FROM aws_comprehend.detect_sentiment('I love it', 'en')` returns POSITIVE).
2. Every review is scored **once** and the result stored. Questions must not trigger Comprehend calls.
3. The agent's tool answers in under 1 second, reading a **curated view**. `trail_desk_app` gets no access to raw reviews or to `aws_comprehend`.
4. Least privilege for the Aurora ML role.

## Done when

`check.py` reports 6/6 checks passed.

## Investigation toolkit

```bash
aws rds describe-db-clusters --db-cluster-identifier riverbend-db-shop --query 'DBClusters[0].AssociatedRoles'
aws iam get-role-policy --role-name <aurora ml role> --policy-name comprehend
python3 common/dbsql.py --sql "SELECT extname FROM pg_extension"
python3 common/dbsql.py --sql "SELECT sentiment, confidence FROM aws_comprehend.detect_sentiment('The seams leaked on day one', 'en')"
aws logs tail /aws/lambda/riverbend-d14-review-insights --since 10m
```

## Hint ladder

<details><summary>Hint 1: the function doesn't exist</summary>Which extension provides the <code>aws_comprehend</code> schema? Who may create it?</details>
<details><summary>Hint 2: Aurora can't reach Comprehend</summary>A role association names a <b>feature</b>. Which feature is this one for? And which Comprehend API does <code>detect_sentiment</code> need?</details>
<details><summary>Hint 3: the tool</summary>What does the tool's query cost (time and money) per question, and what may <code>trail_desk_app</code> read? Look at how D1 exposed data to the agent.</details>

## Debrief questions

1. Why score reviews in a batch job rather than on every question? When would on-demand scoring be acceptable?
2. What are the pros and cons of calling ML from SQL (Aurora ML) compared with an external pipeline?
3. How would you score new reviews as they arrive?
4. Which other Aurora ML features could this agent use (Bedrock and SageMaker functions)?
