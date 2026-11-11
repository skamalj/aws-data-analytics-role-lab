#!/usr/bin/env bash
# Run an Athena query as one of the persona roles.
#   ./labs/06-securing-the-data-lake/infra/as_role.sh eu-analyst "SELECT * FROM riverbend_secure.orders LIMIT 5"
#   ./labs/06-securing-the-data-lake/infra/as_role.sh marketing  "SELECT * FROM riverbend_secure.customers LIMIT 5"
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
PERSONA="${1:?persona: eu-analyst | marketing}"; SQL="${2:?sql}"
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
CREDS=$(aws sts assume-role --role-arn "arn:aws:iam::$ACCOUNT:role/cq-da-06-$PERSONA" \
  --role-session-name "lab06-$PERSONA" --query Credentials --output json)
export AWS_ACCESS_KEY_ID=$(echo "$CREDS" | python3 -c 'import json,sys;print(json.load(sys.stdin)["AccessKeyId"])')
export AWS_SECRET_ACCESS_KEY=$(echo "$CREDS" | python3 -c 'import json,sys;print(json.load(sys.stdin)["SecretAccessKey"])')
export AWS_SESSION_TOKEN=$(echo "$CREDS" | python3 -c 'import json,sys;print(json.load(sys.stdin)["SessionToken"])')
echo ">> as cq-da-06-$PERSONA"
python3 "$ROOT/common/athena_run.py" --workgroup cq-da-06 --sql "$SQL"
