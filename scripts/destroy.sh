#!/usr/bin/env bash
# Tear down a lab's starting environment.
# Run the lab's solution cleanup (solutions/<lab>/cleanup.sh) FIRST if you built
# anything by hand, otherwise resources you created yourself will keep billing.
#   ./scripts/destroy.sh 01-data-lakes
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LAB="${1:?usage: destroy.sh <lab-folder>}"
STACK="cq-da-${LAB%%-*}"
if [[ -x "$ROOT/labs/$LAB/infra/pre-destroy.sh" ]]; then
  "$ROOT/labs/$LAB/infra/pre-destroy.sh" "$STACK"
fi
echo ">> Emptying buckets owned by $STACK"
python3 "$ROOT/common/awslab.py" empty-buckets "$STACK" || true
echo ">> Deleting stack $STACK"
aws cloudformation delete-stack --stack-name "$STACK"
aws cloudformation wait stack-delete-complete --stack-name "$STACK"
echo ">> $STACK deleted"
