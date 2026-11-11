#!/usr/bin/env bash
# Reference solution for Lab 03.
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; . "$ROOT/common/lib.sh"
STACK=cq-da-03
SPILL=$(stack_output $STACK SpillBucket)
LAKE=$(stack_output $STACK LakeBucket)
REGION=$(aws configure get region || echo "${AWS_REGION:-us-east-1}"); REGION=${AWS_REGION:-$REGION}
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
CONNECTOR_STACK=serverlessrepo-cq-da-03-ddb-connector   # SAR prefixes stack names with "serverlessrepo-"
FN=riverbend-ddb
# The AWS-published connector application. 292517598671 is the AWS Athena account that owns it.
APP_ID=arn:aws:serverlessrepo:us-east-1:292517598671:applications/AthenaDynamoDBConnector

echo ">> Task 1: deploy the DynamoDB connector from the Serverless Application Repository"
if ! aws cloudformation describe-stacks --stack-name $CONNECTOR_STACK >/dev/null 2>&1; then
  CS=$(aws serverlessrepo create-cloud-formation-change-set \
        --application-id $APP_ID \
        --stack-name cq-da-03-ddb-connector \
        --capabilities CAPABILITY_IAM CAPABILITY_RESOURCE_POLICY \
        --parameter-overrides Name=AthenaCatalogName,Value=$FN Name=SpillBucket,Value=$SPILL \
        --query ChangeSetId --output text)
  aws cloudformation wait change-set-create-complete --change-set-name "$CS"
  aws cloudformation execute-change-set --change-set-name "$CS"
  aws cloudformation wait stack-create-complete --stack-name $CONNECTOR_STACK
fi

echo ">> Task 2: register the data catalog"
try aws athena create-data-catalog --name ddb --type LAMBDA \
  --description "Riverbend CRM in DynamoDB" \
  --parameters function=arn:aws:lambda:$REGION:$ACCOUNT:function:$FN

echo ">> Tasks 3-5"
athena cq-da-03 -e "DROP TABLE IF EXISTS riverbend_fed.campaign_list" >/dev/null
aws s3 rm "s3://$LAKE/exports/campaign_list/" --recursive --quiet
TMP=$(mktemp); trap 'rm -f $TMP' EXIT
sed "s/__LAKE_BUCKET__/$LAKE/g" "$ROOT/solutions/03-federated-queries/queries.sql" > "$TMP"
athena cq-da-03 "$TMP"
