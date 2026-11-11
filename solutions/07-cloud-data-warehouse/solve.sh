#!/usr/bin/env bash
# Reference solution for Lab 07 (runs SQL through the Redshift Data API).
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; . "$ROOT/common/lib.sh"
HERE="$ROOT/solutions/07-cloud-data-warehouse"
STACK=cq-da-07
BUCKET=$(stack_output $STACK StagingBucket)
SECRET=$(aws redshift-serverless get-namespace --namespace-name cq-da-07 \
          --query namespace.adminPasswordSecretArn --output text)
TMP=$(mktemp -d); trap 'rm -rf $TMP' EXIT
rs() { python3 "$ROOT/common/redshift_run.py" --workgroup cq-da-07 --database riverbend --secret-arn "$SECRET" --file "$1"; }

for f in 01_schema 02_load 03_queries; do
  sed "s/__STAGING_BUCKET__/$BUCKET/g" "$HERE/$f.sql" > "$TMP/$f.sql"
  rs "$TMP/$f.sql"
done

echo ">> Task 7: cost guard-rail, 4 RPU-hours per day, log and emit a metric when breached"
WG_ARN=$(aws redshift-serverless get-workgroup --workgroup-name cq-da-07 --query workgroup.workgroupArn --output text)
if [[ -z "$(aws redshift-serverless list-usage-limits --resource-arn "$WG_ARN" --query 'usageLimits[0].usageLimitId' --output text | grep -v None)" ]]; then
  aws redshift-serverless create-usage-limit --resource-arn "$WG_ARN" \
    --usage-type serverless-compute --amount 4 --period daily --breach-action emit-metric
fi
aws redshift-serverless update-workgroup --workgroup-name cq-da-07 --max-capacity 32 >/dev/null || true
