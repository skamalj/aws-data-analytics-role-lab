#!/usr/bin/env bash
# Reference solution for Lab 10.
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; . "$ROOT/common/lib.sh"
HERE="$ROOT/solutions/10-real-time-data-processing"
S=cq-da-10
FN=cq-da-10-freezer-processor
ENDPOINT=$(stack_output $S OpenSearchEndpoint)
QURL=$(stack_output $S FailedRecordsQueueUrl)
QARN=$(stack_output $S FailedRecordsQueueArn)
ROLE=$(stack_output $S ProcessorRoleArn)
STREAM_ARN=$(stack_output $S StreamArn)

echo ">> Tasks 2-3: OpenSearch security role mapping, index template, index patterns"
python3 "$HERE/setup_opensearch.py" --stack $S

echo ">> Task 4: processor Lambda"
TMP=$(mktemp -d); trap 'rm -rf $TMP' EXIT
(cd "$HERE/processor" && zip -q "$TMP/fn.zip" app.py)
ENV="Variables={OPENSEARCH_ENDPOINT=$ENDPOINT,FAILED_QUEUE_URL=$QURL,ALERT_AVG_C=-15}"
if aws lambda get-function --function-name $FN >/dev/null 2>&1; then
  aws lambda update-function-code --function-name $FN --zip-file "fileb://$TMP/fn.zip" >/dev/null
else
  aws lambda create-function --function-name $FN --runtime python3.12 --handler app.handler \
    --role "$ROLE" --timeout 60 --memory-size 256 --zip-file "fileb://$TMP/fn.zip" \
    --environment "$ENV" >/dev/null
fi
aws lambda wait function-active-v2 --function-name $FN

echo ">> Task 5: event source mapping with 60 s tumbling windows and an SQS on-failure destination"
if [[ -z "$(aws lambda list-event-source-mappings --function-name $FN --query 'EventSourceMappings[0].UUID' --output text | grep -v None)" ]]; then
  aws lambda create-event-source-mapping --function-name $FN --event-source-arn "$STREAM_ARN" \
    --starting-position LATEST --batch-size 1000 --maximum-batching-window-in-seconds 5 \
    --tumbling-window-in-seconds 60 --bisect-batch-on-function-error \
    --maximum-retry-attempts 3 --maximum-record-age-in-seconds 3600 \
    --destination-config "OnFailure={Destination=$QARN}" >/dev/null
fi

echo ">> Waiting 6 minutes for windows, alerts and at least one malformed record"
sleep 360
python3 "$HERE/check.py" --stack $S
