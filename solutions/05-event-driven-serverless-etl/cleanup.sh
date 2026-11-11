#!/usr/bin/env bash
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; . "$ROOT/common/lib.sh"
aws cloudformation delete-stack --stack-name cq-da-05-solution
aws cloudformation wait stack-delete-complete --stack-name cq-da-05-solution
echo "Lab 05 pipeline removed. Now run ./scripts/destroy.sh 05-event-driven-serverless-etl"
