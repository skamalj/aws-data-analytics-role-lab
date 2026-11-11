#!/usr/bin/env bash
# Deploy the starting environment for one lab and seed its sample data.
#   ./scripts/deploy.sh 01-data-lakes [ParamKey=Value ...]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LAB="${1:?usage: deploy.sh <lab-folder> [ParamKey=Value ...]}"; shift || true
DIR="$ROOT/labs/$LAB"
[[ -f "$DIR/infra/template.yaml" ]] || { echo "no template at $DIR/infra/template.yaml"; exit 1; }
STACK="cq-da-${LAB%%-*}"
REGION="$(aws configure get region || true)"; REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-$REGION}}"
echo ">> Deploying $LAB as stack $STACK in ${REGION:-<default region>}"

PARAMS=()
[[ $# -gt 0 ]] && PARAMS=(--parameter-overrides "$@")
aws cloudformation deploy \
  --template-file "$DIR/infra/template.yaml" \
  --stack-name "$STACK" \
  --capabilities CAPABILITY_NAMED_IAM CAPABILITY_AUTO_EXPAND \
  --tags Project=cloud-quest-data-analytics Lab="$LAB" \
  --no-fail-on-empty-changeset "${PARAMS[@]}"

if [[ -f "$DIR/infra/seed.py" ]]; then
  echo ">> Seeding sample data"
  python3 "$DIR/infra/seed.py" --stack "$STACK"
fi

echo ">> Stack outputs (you will need these in the lab):"
python3 "$ROOT/common/awslab.py" outputs "$STACK" | sed 's/^/   /'
echo ">> Now open labs/$LAB/README.md and start solving."
