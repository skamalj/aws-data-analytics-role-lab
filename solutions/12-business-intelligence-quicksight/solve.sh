#!/usr/bin/env bash
# Reference solution for Lab 12 (data source, SPICE dataset, RLS, refresh schedule).
#   QS_AUTHOR=<quicksight user name> [QS_READER=<reader user name>] ./solve.sh
# Prerequisite (console, once): QuickSight subscribed, and in Manage QuickSight >
# Security & permissions, access granted to Athena and to the cq-da-12-lake-* and cq-da-12-athena-* buckets.
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; . "$ROOT/common/lib.sh"
HERE="$ROOT/solutions/12-business-intelligence-quicksight"
S=cq-da-12
: "${QS_AUTHOR:?set QS_AUTHOR to your QuickSight user name (aws quicksight list-users ...)}"
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
REGION=${AWS_REGION:-$(aws configure get region)}
LAKE=$(stack_output $S LakeBucket)

echo ">> RLS rules: the author sees every region, the reader only EU"
TMP=$(mktemp); trap 'rm -f $TMP' EXIT
{ echo "username,region"
  for r in NA EU APAC LATAM; do echo "$QS_AUTHOR,$r"; done
  [[ -n "${QS_READER:-}" ]] && echo "$QS_READER,EU"
} > "$TMP"
aws s3 cp "$TMP" "s3://$LAKE/rls/rules.csv"

echo ">> Data source, datasets (SPICE import starts automatically), daily refresh"
aws cloudformation deploy --stack-name cq-da-12-solution --template-file "$HERE/template.yaml" \
  --no-fail-on-empty-changeset --parameter-overrides LakeBucket="$LAKE" \
  AuthorUserArn="arn:aws:quicksight:$REGION:$ACCOUNT:user/default/$QS_AUTHOR"

aws quicksight list-ingestions --aws-account-id "$ACCOUNT" --data-set-id cq-da-12-sales \
  --query 'Ingestions[0].{status:IngestionStatus,rows:RowInfo.RowsIngested}' --output table

echo ">> Check values straight from Athena"
athena cq-da-12 "$HERE/queries.sql"
echo ">> Now build the analysis in the QuickSight console (README, section 'Analysis')."
