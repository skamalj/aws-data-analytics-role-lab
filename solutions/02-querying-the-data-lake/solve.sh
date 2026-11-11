#!/usr/bin/env bash
# Reference solution for Lab 02.
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; . "$ROOT/common/lib.sh"
STACK=cq-da-02
CURATED=$(stack_output $STACK CuratedBucket)
RESULTS=$(stack_output $STACK AthenaResultsBucket)
HERE="$ROOT/solutions/02-querying-the-data-lake"
TMP=$(mktemp); trap 'rm -f $TMP' EXIT

# Re-runnable: drop the CTAS table and its data first
athena cq-da-02 -e "DROP TABLE IF EXISTS riverbend_lake.orders_parquet" >/dev/null
aws s3 rm "s3://$CURATED/orders_parquet/" --recursive --quiet

sed "s/__CURATED_BUCKET__/$CURATED/g" "$HERE/queries.sql" > "$TMP"
athena cq-da-02 "$TMP"

echo ">> Task 6: guard-rail workgroup"
try aws athena create-work-group --name cq-da-02-analysts --configuration \
  "ResultConfiguration={OutputLocation=s3://$RESULTS/analysts/},EnforceWorkGroupConfiguration=true,BytesScannedCutoffPerQuery=10485760,PublishCloudWatchMetricsEnabled=true"

echo ">> CSV query in analysts workgroup (expected to FAIL: data limit exceeded)"
athena cq-da-02-analysts -e "SELECT COUNT(*), ROUND(SUM(total_amount),2) FROM riverbend_lake.orders_csv WHERE status='COMPLETED' AND region='EU' AND order_ts >= TIMESTAMP '2024-03-01 00:00:00' AND order_ts < TIMESTAMP '2024-04-01 00:00:00'" || true
echo ">> Parquet query in analysts workgroup (expected to SUCCEED)"
athena cq-da-02-analysts -e "SELECT COUNT(*), ROUND(SUM(total_amount),2) FROM riverbend_lake.orders_parquet WHERE status='COMPLETED' AND region='EU' AND order_year=2024 AND order_month=3"
