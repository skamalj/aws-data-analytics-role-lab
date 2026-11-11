#!/usr/bin/env bash
# Reference solution for Lab 08.
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; . "$ROOT/common/lib.sh"
HERE="$ROOT/solutions/08-daily-batch-extraction"
INFRA="$ROOT/labs/08-daily-batch-extraction/infra"
S=cq-da-08
o() { stack_output $S "$1"; }

aws s3 cp "$HERE/extract_orders.py" "s3://$(o ScriptsBucket)/glue/extract_orders.py"
aws cloudformation deploy --stack-name cq-da-08-solution --template-file "$HERE/template.yaml" \
  --no-fail-on-empty-changeset --parameter-overrides \
  ClusterEndpoint="$(o ClusterEndpoint)" DbSecretArn="$(o DbSecretArn)" \
  SubnetId="$(o PrivateSubnetA)" SubnetAZ="$(o PrivateSubnetAZ)" \
  GlueSecurityGroupId="$(o GlueSecurityGroupId)" ExtractBucket="$(o ExtractBucket)" \
  ScriptsBucket="$(o ScriptsBucket)" GlueJobRoleArn="$(o GlueJobRoleArn)" \
  StepFunctionsRoleArn="$(o StepFunctionsRoleArn)" NotificationsTopicArn="$(o NotificationsTopicArn)"
SM=$(stack_output cq-da-08-solution StateMachineArn)

run_sm() {   # run_sm '<json input>'
  local arn; arn=$(aws stepfunctions start-execution --state-machine-arn "$SM" --input "$1" --query executionArn --output text)
  echo -n ">> execution $1 "
  while true; do
    local st; st=$(aws stepfunctions describe-execution --execution-arn "$arn" --query status --output text)
    [[ "$st" != "RUNNING" ]] && break; echo -n "."; sleep 15
  done
  echo " $st: $(aws stepfunctions describe-execution --execution-arn "$arn" --query output --output text)"
}

echo ">> Task 4: initial full load as of 2024-06-30"
run_sm '{"run_date":"2024-06-30","mode":"full"}'
echo ">> Task 6: two business days, extracted incrementally"
python3 "$INFRA/new_day.py" --date 2024-07-01
run_sm '{"run_date":"2024-07-01"}'
python3 "$INFRA/new_day.py" --date 2024-07-02
run_sm '{"run_date":"2024-07-02"}'
echo ">> Idempotency: re-running 2024-07-01 must not change any numbers"
run_sm '{"run_date":"2024-07-01"}'

athena cq-da-08 "$HERE/queries.sql"
