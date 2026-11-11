#!/usr/bin/env bash
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; . "$ROOT/common/lib.sh"
FN=cq-da-10-freezer-processor
for u in $(aws lambda list-event-source-mappings --function-name $FN --query 'EventSourceMappings[].UUID' --output text 2>/dev/null); do
  try aws lambda delete-event-source-mapping --uuid "$u"
done
try aws lambda delete-function --function-name $FN
echo "Processor removed. Now run ./scripts/destroy.sh 10-real-time-data-processing (deletes OpenSearch, stream, queue)"
