#!/usr/bin/env bash
# Reference solution for Lab 05.  Optional: NOTIFY_EMAIL=you@example.com ./solve.sh
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; . "$ROOT/common/lib.sh"
HERE="$ROOT/solutions/05-event-driven-serverless-etl"
STACK=cq-da-05
SCRIPTS=$(stack_output $STACK ScriptsBucket)

echo ">> Upload the Glue script"
aws s3 cp "$HERE/etl_orders.py" "s3://$SCRIPTS/glue/etl_orders.py"

echo ">> Deploy the pipeline (Glue job, Lambda, EventBridge rules, SNS, curated tables)"
aws cloudformation deploy --stack-name cq-da-05-solution --template-file "$HERE/template.yaml" \
  --no-fail-on-empty-changeset --parameter-overrides \
  LandingBucket="$(stack_output $STACK LandingBucket)" \
  CuratedBucket="$(stack_output $STACK CuratedBucket)" \
  ScriptsBucket="$SCRIPTS" \
  GlueJobRoleArn="$(stack_output $STACK GlueJobRoleArn)" \
  TriggerLambdaRoleArn="$(stack_output $STACK TriggerLambdaRoleArn)" \
  NotificationEmail="${NOTIFY_EMAIL:-}"

echo ">> Drop days 1-3 and the corrupt day-4 file"
python3 "$ROOT/labs/05-event-driven-serverless-etl/infra/drop_files.py"
python3 "$ROOT/labs/05-event-driven-serverless-etl/infra/drop_files.py" --bad

echo -n ">> Waiting for 4 Glue job runs to finish"
sleep 30
while true; do
  RUNS=$(aws glue get-job-runs --job-name cq-da-05-orders-etl --max-items 10 \
          --query 'JobRuns[].JobRunState' --output text)
  DONE=$(echo "$RUNS" | tr '\t' '\n' | grep -cE 'SUCCEEDED|FAILED|TIMEOUT|ERROR|STOPPED' || true)
  [[ "$DONE" -ge 4 ]] && break
  echo -n "."; sleep 20
done
echo; aws glue get-job-runs --job-name cq-da-05-orders-etl --max-items 4 \
  --query 'JobRuns[].[Arguments."--source_key",JobRunState,ExecutionTime]' --output table

athena cq-da-05 "$HERE/queries.sql"
