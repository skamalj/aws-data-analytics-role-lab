#!/usr/bin/env bash
# Reference solution for Lab 09.
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; . "$ROOT/common/lib.sh"
HERE="$ROOT/solutions/09-streaming-ingestion"
S=cq-da-09
BUCKET=$(stack_output $S RawEventsBucket)
INSTANCE=$(stack_output $S ProducerInstanceId)

echo ">> Tasks 1+3: stream and Firehose"
aws cloudformation deploy --stack-name cq-da-09-solution --template-file "$HERE/template.yaml" \
  --no-fail-on-empty-changeset --parameter-overrides \
  RawEventsBucket="$BUCKET" FirehoseRoleArn="$(stack_output $S FirehoseRoleArn)"

echo ">> Task 2: peek at the stream (the producer polls every 30 s for the stream to appear)"
sleep 45
SHARD=$(aws kinesis list-shards --stream-name riverbend-clickstream --query 'Shards[0].ShardId' --output text)
IT=$(aws kinesis get-shard-iterator --stream-name riverbend-clickstream --shard-id "$SHARD" \
      --shard-iterator-type LATEST --query ShardIterator --output text)
sleep 5
aws kinesis get-records --shard-iterator "$IT" --limit 3 --query 'Records[].Data' --output text \
  | tr '\t' '\n' | head -3 | while read -r d; do echo "$d" | base64 -d; done

echo ">> Waiting ~3 minutes for Firehose to flush the first buffers to S3"
sleep 180
aws s3 ls "s3://$BUCKET/events/" --recursive | head -5

echo ">> Task 4: Athena"
TMP=$(mktemp); trap 'rm -f $TMP' EXIT
sed "s/__EVENTS_BUCKET__/$BUCKET/g" "$HERE/queries.sql" > "$TMP"
athena cq-da-09 "$TMP"

echo ">> Task 5: burst to 1,500 events/s (more than 1 shard accepts), then scale out"
aws ssm send-command --instance-ids "$INSTANCE" --document-name AWS-RunShellScript \
  --parameters 'commands=["sed -i s/^RATE=.*/RATE=1500/ /etc/clickstream-producer.env","systemctl restart clickstream-producer"]' >/dev/null
echo "   bursting for 3 minutes; watch WriteProvisionedThroughputExceeded in the Kinesis console"
sleep 180
aws kinesis update-shard-count --stream-name riverbend-clickstream --target-shard-count 2 --scaling-type UNIFORM_SCALING
echo "   resharding to 2 shards (takes a few minutes); afterwards throttling stops"
sleep 240
aws ssm send-command --instance-ids "$INSTANCE" --document-name AWS-RunShellScript \
  --parameters 'commands=["sed -i s/^RATE=.*/RATE=20/ /etc/clickstream-producer.env","systemctl restart clickstream-producer"]' >/dev/null
echo "   producer back to 20 events/s"
