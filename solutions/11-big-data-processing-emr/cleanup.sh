#!/usr/bin/env bash
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; . "$ROOT/common/lib.sh"
for id in $(aws emr-serverless list-applications --query "applications[?name=='cq-da-11-spark' && state!='TERMINATED'].id" --output text); do
  try aws emr-serverless stop-application --application-id "$id"
  sleep 20
  try aws emr-serverless delete-application --application-id "$id"
done
try aws glue delete-table --database-name riverbend_emr --name sessions
echo "Lab 11 resources removed. Now run ./scripts/destroy.sh 11-big-data-processing-emr"
