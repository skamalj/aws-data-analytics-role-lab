#!/usr/bin/env bash
# Reference solution for Lab 04.
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; . "$ROOT/common/lib.sh"
STACK=cq-da-04
B=$(stack_output $STACK LandingBucket)
ROLE=$(stack_output $STACK GlueCrawlerRoleName)
DB=riverbend_catalog
CRAWLER=cq-da-04-landing-crawler

try aws glue create-database --database-input Name=$DB

echo ">> Custom classifier for headerless pipe-delimited POS files"
try aws glue create-classifier --csv-classifier '{
  "Name": "cq-da-04-pos-psv",
  "Delimiter": "|",
  "QuoteSymbol": "\"",
  "ContainsHeader": "ABSENT",
  "Header": ["order_id","order_ts","store_id","product_id","quantity","total_amount"],
  "DisableValueTrimming": false,
  "AllowSingleColumn": false
}'

TARGETS=$(cat <<JSON
{"S3Targets":[
  {"Path":"s3://$B/web_orders/","Exclusions":["**.tmp","**_SUCCESS"]},
  {"Path":"s3://$B/store_sales/"},
  {"Path":"s3://$B/returns/"}
]}
JSON
)
try aws glue create-crawler --name $CRAWLER --role "$ROLE" --database-name $DB \
  --table-prefix lnd_ --classifiers cq-da-04-pos-psv --targets "$TARGETS" \
  --schema-change-policy UpdateBehavior=UPDATE_IN_DATABASE,DeleteBehavior=LOG
run_crawler $CRAWLER
aws glue get-tables --database-name $DB --query 'TableList[].Name' --output text

echo ">> Task 4/5: clickstream with partition projection"
TMP=$(mktemp); trap 'rm -f $TMP' EXIT
sed "s/__LANDING_BUCKET__/$B/g" "$ROOT/solutions/04-populating-the-data-catalog/clickstream.sql" > "$TMP"
athena cq-da-04 "$TMP"

echo ">> Task 6: schedule + incremental crawls"
# Incremental crawling requires the schema change policy to LOG updates and deletes.
aws glue update-crawler --name $CRAWLER \
  --schedule "cron(0 3 * * ? *)" \
  --recrawl-policy RecrawlBehavior=CRAWL_NEW_FOLDERS_ONLY \
  --schema-change-policy UpdateBehavior=LOG,DeleteBehavior=LOG
python3 "$ROOT/labs/04-populating-the-data-catalog/infra/add_month.py" --stack $STACK
run_crawler $CRAWLER
aws glue get-partitions --database-name $DB --table-name lnd_web_orders \
  --query 'Partitions[].Values' --output text | sort
athena cq-da-04 -e "SELECT COUNT(*) AS web_orders_after_july FROM riverbend_catalog.lnd_web_orders"
