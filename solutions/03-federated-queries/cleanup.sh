#!/usr/bin/env bash
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; . "$ROOT/common/lib.sh"
try athena cq-da-03 -e "DROP TABLE IF EXISTS riverbend_fed.campaign_list"
try aws athena delete-data-catalog --name ddb
if aws cloudformation describe-stacks --stack-name serverlessrepo-cq-da-03-ddb-connector >/dev/null 2>&1; then
  aws cloudformation delete-stack --stack-name serverlessrepo-cq-da-03-ddb-connector
  aws cloudformation wait stack-delete-complete --stack-name serverlessrepo-cq-da-03-ddb-connector
fi
echo "Lab 03 resources removed. Now run ./scripts/destroy.sh 03-federated-queries"
