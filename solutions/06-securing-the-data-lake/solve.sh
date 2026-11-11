#!/usr/bin/env bash
# Reference solution for Lab 06.
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; . "$ROOT/common/lib.sh"
HERE="$ROOT/solutions/06-securing-the-data-lake"
AS="$ROOT/labs/06-securing-the-data-lake/infra/as_role.sh"
STACK=cq-da-06
LAKE=$(stack_output $STACK LakeBucket)
ANALYST=$(stack_output $STACK EuAnalystRoleArn)
MARKETING=$(stack_output $STACK MarketingRoleArn)
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
DB=riverbend_secure

echo ">> Before: personas cannot read the data (no S3 permissions, no LF grants)"
"$AS" marketing "SELECT * FROM $DB.customers LIMIT 3" || true

echo ">> Task 1: make me a data lake administrator"
python3 "$HERE/lf_admin.py" add

echo ">> Task 2: register the lake bucket with Lake Formation"
try aws lakeformation register-resource --resource-arn "arn:aws:s3:::$LAKE" --use-service-linked-role

echo ">> Task 3: switch the database from IAM-only access to Lake Formation permissions"
try aws lakeformation revoke-permissions --principal DataLakePrincipalIdentifier=IAM_ALLOWED_PRINCIPALS \
  --resource "{\"Table\":{\"DatabaseName\":\"$DB\",\"TableWildcard\":{}}}" --permissions ALL
try aws lakeformation revoke-permissions --principal DataLakePrincipalIdentifier=IAM_ALLOWED_PRINCIPALS \
  --resource "{\"Database\":{\"Name\":\"$DB\"}}" --permissions ALL
aws glue update-database --name $DB --database-input "{\"Name\":\"$DB\",\"CreateTableDefaultPermissions\":[]}"

echo ">> Task 4: marketing - customers without PII columns, nothing else"
aws lakeformation grant-permissions --principal DataLakePrincipalIdentifier=$MARKETING \
  --resource "{\"Database\":{\"Name\":\"$DB\"}}" --permissions DESCRIBE
aws lakeformation grant-permissions --principal DataLakePrincipalIdentifier=$MARKETING \
  --resource "{\"TableWithColumns\":{\"DatabaseName\":\"$DB\",\"Name\":\"customers\",\"ColumnWildcard\":{\"ExcludedColumnNames\":[\"email\",\"phone\"]}}}" \
  --permissions SELECT

echo ">> Task 5: EU analyst - row-level (and one column-level) data cell filters"
try aws lakeformation create-data-cells-filter --table-data "{
  \"TableCatalogId\":\"$ACCOUNT\",\"DatabaseName\":\"$DB\",\"TableName\":\"orders\",\"Name\":\"orders_eu_only\",
  \"RowFilter\":{\"FilterExpression\":\"region = 'EU'\"},\"ColumnWildcard\":{\"ExcludedColumnNames\":[]}}"
try aws lakeformation create-data-cells-filter --table-data "{
  \"TableCatalogId\":\"$ACCOUNT\",\"DatabaseName\":\"$DB\",\"TableName\":\"customers\",\"Name\":\"customers_eu_no_phone\",
  \"RowFilter\":{\"FilterExpression\":\"region = 'EU'\"},\"ColumnWildcard\":{\"ExcludedColumnNames\":[\"phone\"]}}"
aws lakeformation grant-permissions --principal DataLakePrincipalIdentifier=$ANALYST \
  --resource "{\"Database\":{\"Name\":\"$DB\"}}" --permissions DESCRIBE
for F in orders:orders_eu_only customers:customers_eu_no_phone; do
  aws lakeformation grant-permissions --principal DataLakePrincipalIdentifier=$ANALYST \
    --resource "{\"DataCellsFilter\":{\"TableCatalogId\":\"$ACCOUNT\",\"DatabaseName\":\"$DB\",\"TableName\":\"${F%%:*}\",\"Name\":\"${F##*:}\"}}" \
    --permissions SELECT
done

echo ">> Task 6: verify (grants can take a few seconds to apply)"
sleep 10
"$AS" marketing  "SELECT * FROM $DB.customers LIMIT 3"
"$AS" marketing  "SELECT COUNT(*) FROM $DB.orders" || echo "   (expected: access denied)"
"$AS" eu-analyst "SELECT region, COUNT(*) AS orders, ROUND(SUM(total_amount) FILTER (WHERE status='COMPLETED'),2) AS completed_revenue FROM $DB.orders GROUP BY region"
"$AS" eu-analyst "SELECT region, COUNT(*) AS customers FROM $DB.customers GROUP BY region"
"$AS" eu-analyst "SELECT phone FROM $DB.customers LIMIT 1" || echo "   (expected: column not found / access denied)"
