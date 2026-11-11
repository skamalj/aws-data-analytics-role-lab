#!/usr/bin/env bash
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; . "$ROOT/common/lib.sh"
try athena cq-da-08 -e "DROP VIEW IF EXISTS riverbend_extracts.orders_current"
aws cloudformation delete-stack --stack-name cq-da-08-solution
aws cloudformation wait stack-delete-complete --stack-name cq-da-08-solution
echo "Lab 08 solution removed. Now run ./scripts/destroy.sh 08-daily-batch-extraction (Aurora takes ~10 min to delete)"
