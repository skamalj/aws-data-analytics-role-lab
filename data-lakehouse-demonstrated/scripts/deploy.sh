#!/usr/bin/env bash
# ./scripts/deploy.sh base          shared buckets, Glue database, Athena workgroup, Glue role
# ./scripts/deploy.sh C1 [tf args]  one challenge (setup.py before terraform, post_deploy.py after, if present)
# AUTO_APPROVE=1 skips the terraform confirmation.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ID="${1:?usage: deploy.sh <base|C1..C7> [terraform args]}"; shift
APPROVE=(); [[ "${AUTO_APPROVE:-0}" == "1" ]] && APPROVE=(-auto-approve)
if [[ "$ID" == "base" ]]; then
  terraform -chdir="$ROOT/base/terraform" init -input=false -upgrade >/dev/null
  terraform -chdir="$ROOT/base/terraform" apply "${APPROVE[@]}" "$@"
  exit 0
fi
MDIR="$(ls -d "$ROOT"/missions/"${ID^^}"-* 2>/dev/null | head -1)"
[[ -n "$MDIR" ]] || { echo "no challenge $ID"; exit 1; }
[[ -s "$ROOT/base/terraform/terraform.tfstate" ]] || { echo "run ./scripts/deploy.sh base first"; exit 1; }
if [[ -f "$MDIR/setup.py" ]]; then echo ">> setup ($MDIR/setup.py)"; python3 "$MDIR/setup.py"; fi
terraform -chdir="$MDIR/terraform" init -input=false -upgrade >/dev/null
terraform -chdir="$MDIR/terraform" apply "${APPROVE[@]}" "$@"
if [[ -f "$MDIR/post_deploy.py" ]]; then echo ">> post-deploy ($MDIR/post_deploy.py)"; python3 "$MDIR/post_deploy.py"; fi
echo ">> Deployed ${ID^^}. Brief: ${MDIR#$ROOT/}/README.md   Check: python3 ${MDIR#$ROOT/}/scenarios/check.py"
