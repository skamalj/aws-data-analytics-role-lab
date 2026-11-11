#!/usr/bin/env bash
# Undo every Lake Formation change from this lab, so the account is back to its previous settings.
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; . "$ROOT/common/lib.sh"
STACK=cq-da-06
DB=riverbend_secure
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
LAKE=$(stack_output $STACK LakeBucket 2>/dev/null || true)
for P in "$(stack_output $STACK EuAnalystRoleArn)" "$(stack_output $STACK MarketingRoleArn)"; do
  for RES in $(aws lakeformation list-permissions --principal DataLakePrincipalIdentifier="$P" \
                 --query 'PrincipalResourcePermissions[].Resource' --output json | python3 -c \
                 'import json,sys;[print(json.dumps(r,separators=(",",":"))) for r in json.load(sys.stdin)]'); do
    PERMS=$(aws lakeformation list-permissions --principal DataLakePrincipalIdentifier="$P" --resource "$RES" \
              --query 'PrincipalResourcePermissions[0].Permissions' --output text 2>/dev/null || true)
    if [[ -n "$PERMS" ]]; then
      try aws lakeformation revoke-permissions --principal DataLakePrincipalIdentifier="$P" --resource "$RES" --permissions $PERMS
    fi
  done
done
try aws lakeformation delete-data-cells-filter --table-catalog-id "$ACCOUNT" --database-name $DB --table-name orders --name orders_eu_only
try aws lakeformation delete-data-cells-filter --table-catalog-id "$ACCOUNT" --database-name $DB --table-name customers --name customers_eu_no_phone
# Give IAM back control of the catalog objects, so CloudFormation can delete them.
try aws lakeformation grant-permissions --principal DataLakePrincipalIdentifier=IAM_ALLOWED_PRINCIPALS \
  --resource "{\"Database\":{\"Name\":\"$DB\"}}" --permissions ALL
try aws lakeformation grant-permissions --principal DataLakePrincipalIdentifier=IAM_ALLOWED_PRINCIPALS \
  --resource "{\"Table\":{\"DatabaseName\":\"$DB\",\"TableWildcard\":{}}}" --permissions ALL
if [[ -n "$LAKE" ]]; then try aws lakeformation deregister-resource --resource-arn "arn:aws:s3:::$LAKE"; fi
python3 "$ROOT/solutions/06-securing-the-data-lake/lf_admin.py" restore || true
echo "Lab 06 Lake Formation changes reverted. Now run ./scripts/destroy.sh 06-securing-the-data-lake"
