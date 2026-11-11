#!/usr/bin/env bash
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; . "$ROOT/common/lib.sh"
try athena cq-da-09 -e "DROP TABLE IF EXISTS riverbend_stream.clickstream"
aws cloudformation delete-stack --stack-name cq-da-09-solution
aws cloudformation wait stack-delete-complete --stack-name cq-da-09-solution
echo "Lab 09 stream and Firehose removed. Now run ./scripts/destroy.sh 09-streaming-ingestion"
