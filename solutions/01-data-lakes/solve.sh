#!/usr/bin/env bash
# Reference solution for Lab 01, using the AWS CLI. Safe to re-run.
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; . "$ROOT/common/lib.sh"
STACK=cq-da-01
RAW=$(stack_output $STACK RawBucket)
ROLE=$(stack_output $STACK GlueCrawlerRoleName)
DB=riverbend_raw
CRAWLER=cq-da-01-raw-crawler
CLASSIFIER=cq-da-01-csv-with-header

echo ">> Task 1: database"
try aws glue create-database --database-input "Name=$DB,Description=Riverbend raw exports"

echo ">> Task 3 (fix up front): CSV classifier that always treats row 1 as a header"
try aws glue create-classifier --csv-classifier \
  "Name=$CLASSIFIER,Delimiter=',',QuoteSymbol='\"',ContainsHeader=PRESENT"

echo ">> Task 2: crawler"
# If an earlier run already created customers with col0..colN, drop it so it is re-created cleanly.
if aws glue get-table --database-name $DB --name customers --query 'Table.StorageDescriptor.Columns[0].Name' --output text 2>/dev/null | grep -q '^col0$'; then
  aws glue delete-table --database-name $DB --name customers
fi
try aws glue create-crawler --name $CRAWLER --role "$ROLE" --database-name $DB \
  --classifiers $CLASSIFIER \
  --targets "{\"S3Targets\":[{\"Path\":\"s3://$RAW/sales/\"}]}"
aws glue update-crawler --name $CRAWLER --classifiers $CLASSIFIER >/dev/null
run_crawler $CRAWLER

aws glue get-tables --database-name $DB \
  --query 'TableList[].{table:Name,columns:join(`,`, StorageDescriptor.Columns[].Name)}' --output table

echo ">> Task 4: queries"
athena cq-da-01 "$ROOT/solutions/01-data-lakes/queries.sql" --database $DB

echo ">> Task 5: saved query"
if ! aws athena list-named-queries --work-group cq-da-01 --query NamedQueryIds --output text | grep -q .; then
  aws athena create-named-query --name revenue-by-region --database $DB --work-group cq-da-01 \
    --query-string "SELECT region, COUNT(*) AS orders, ROUND(SUM(total_amount),2) AS revenue FROM riverbend_raw.orders WHERE status='COMPLETED' GROUP BY region ORDER BY revenue DESC"
fi
