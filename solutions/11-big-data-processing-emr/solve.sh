#!/usr/bin/env bash
# Reference solution for Lab 11 (EMR Serverless).
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; . "$ROOT/common/lib.sh"
HERE="$ROOT/solutions/11-big-data-processing-emr"
S=cq-da-11
DATA=$(stack_output $S DataBucket)
CODE=$(stack_output $S CodeBucket)
ROLE=$(stack_output $S JobRuntimeRoleArn)
APP_NAME=cq-da-11-spark

aws s3 cp "$HERE/sessionize.py" "s3://$CODE/jobs/sessionize.py"

echo ">> Task 1: EMR Serverless application (latest emr-7.x release)"
APP_ID=$(aws emr-serverless list-applications --query "applications[?name=='$APP_NAME' && state!='TERMINATED'].id | [0]" --output text)
if [[ "$APP_ID" == "None" || -z "$APP_ID" ]]; then
  RELEASE=$(aws emr-serverless list-release-labels --query 'releaseLabels' --output text | tr '\t' '\n' \
            | grep '^emr-7\.' | sort -t. -k2,2n -k3,3n | tail -1)
  echo "   release $RELEASE"
  APP_ID=$(aws emr-serverless create-application --name $APP_NAME --type SPARK --release-label "$RELEASE" \
    --auto-stop-configuration enabled=true,idleTimeoutMinutes=5 \
    --maximum-capacity cpu=16vCPU,memory=64GB \
    --query applicationId --output text)
fi
echo "   application $APP_ID"

echo ">> Task 2: submit the job"
SUBMIT="--conf spark.hadoop.hive.metastore.client.factory.class=com.amazonaws.glue.catalog.metastore.AWSGlueDataCatalogHiveClientFactory \
--conf spark.driver.cores=1 --conf spark.driver.memory=4g \
--conf spark.executor.cores=2 --conf spark.executor.memory=4g \
--conf spark.executor.instances=2 --conf spark.dynamicAllocation.maxExecutors=4"
JOB=$(aws emr-serverless start-job-run --application-id "$APP_ID" --execution-role-arn "$ROLE" \
  --name sessionize --job-driver "{\"sparkSubmit\":{
      \"entryPoint\":\"s3://$CODE/jobs/sessionize.py\",
      \"entryPointArguments\":[\"s3://$DATA/clickstream/\",\"s3://$DATA/curated/sessions/\"],
      \"sparkSubmitParameters\":\"$SUBMIT\"}}" \
  --configuration-overrides "{\"monitoringConfiguration\":{\"s3MonitoringConfiguration\":{\"logUri\":\"s3://$CODE/logs/\"}}}" \
  --query jobRunId --output text)
echo -n "   job $JOB "
while true; do
  ST=$(aws emr-serverless get-job-run --application-id "$APP_ID" --job-run-id "$JOB" --query jobRun.state --output text)
  [[ "$ST" =~ ^(SUCCESS|FAILED|CANCELLED)$ ]] && break
  echo -n "."; sleep 20
done
echo " $ST"
aws emr-serverless get-job-run --application-id "$APP_ID" --job-run-id "$JOB" \
  --query 'jobRun.{state:state,details:stateDetails,billed:totalResourceUtilization}' --output json
[[ "$ST" == "SUCCESS" ]] || { echo "see logs under s3://$CODE/logs/applications/$APP_ID/jobs/$JOB/"; exit 1; }

echo ">> Task 3: analyse in Athena"
athena cq-da-11 "$HERE/queries.sql"
