#!/usr/bin/env bash
# Remove everything the lab asked you to build (not the starting stack).
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; . "$ROOT/common/lib.sh"
try aws glue delete-crawler --name cq-da-01-raw-crawler
try aws glue delete-classifier --name cq-da-01-csv-with-header
try aws glue delete-database --name riverbend_raw
for id in $(aws athena list-named-queries --work-group cq-da-01 --query NamedQueryIds --output text 2>/dev/null); do
  try aws athena delete-named-query --named-query-id "$id"
done
echo "Lab 01 resources removed. Now run ./scripts/destroy.sh 01-data-lakes"
