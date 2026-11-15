#!/usr/bin/env bash
# ./scripts/deploy.sh base              shared Aurora cluster + schema/data/roles (needed by D1, D2, D4, D5)
# ./scripts/deploy.sh D1 [tf args]      a mission (runs its setup.py SQL first, if it has one)
# AUTO_APPROVE=1 to skip the terraform confirmation.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ID="${1:?usage: deploy.sh <base|D1..D5> [terraform args]}"; shift
APPROVE=(); [[ "${AUTO_APPROVE:-0}" == "1" ]] && APPROVE=(-auto-approve)
if [[ "$ID" == "base" ]]; then
  terraform -chdir="$ROOT/base/terraform" init -input=false -upgrade >/dev/null
  terraform -chdir="$ROOT/base/terraform" apply "${APPROVE[@]}" "$@"
  python3 "$ROOT/base/seed.py"
  exit 0
fi
MDIR="$(ls -d "$ROOT"/missions/"${ID^^}"-* 2>/dev/null | head -1)"
[[ -n "$MDIR" ]] || { echo "no mission $ID"; exit 1; }
NEEDS_BASE=0
if [[ ! -d "$MDIR/terraform" ]] || grep -q terraform_remote_state "$MDIR"/terraform/*.tf; then NEEDS_BASE=1; fi
if [[ "$NEEDS_BASE" == 1 && ! -s "$ROOT/base/terraform/terraform.tfstate" ]]; then
  echo "Mission ${ID^^} uses the shared database: run ./scripts/deploy.sh base first."; exit 1
fi
if [[ -d "$MDIR/terraform" ]] && grep -q agent_base "$MDIR"/terraform/*.tf; then "$ROOT/common/build_agent.sh" "$MDIR"; fi
if [[ -f "$MDIR/setup.py" ]]; then echo ">> database setup ($MDIR/setup.py)"; python3 "$MDIR/setup.py"; fi
if [[ -d "$MDIR/terraform" ]]; then
  terraform -chdir="$MDIR/terraform" init -input=false -upgrade >/dev/null
  terraform -chdir="$MDIR/terraform" apply "${APPROVE[@]}" "$@"
fi
if [[ -f "$MDIR/post_deploy.py" ]]; then echo ">> post-deploy ($MDIR/post_deploy.py)"; python3 "$MDIR/post_deploy.py"; fi
echo ">> Deployed ${ID^^}. Handout: ${MDIR#$ROOT/}/README.md"
