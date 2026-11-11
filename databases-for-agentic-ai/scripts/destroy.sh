#!/usr/bin/env bash
# ./scripts/destroy.sh D1      destroy one mission
# ./scripts/destroy.sh base    destroy the shared database (destroy D1/D2/D4/D5 first)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ID="${1:?usage: destroy.sh <base|D1..D5>}"; shift || true
APPROVE=(); [[ "${AUTO_APPROVE:-0}" == "1" ]] && APPROVE=(-auto-approve)
if [[ "$ID" == "base" ]]; then
  terraform -chdir="$ROOT/base/terraform" destroy "${APPROVE[@]}" "$@"; exit 0
fi
MDIR="$(ls -d "$ROOT"/missions/"${ID^^}"-* 2>/dev/null | head -1)"
[[ -f "$MDIR/terraform/build/agent.zip" ]] || "$ROOT/common/build_agent.sh" "$MDIR"
terraform -chdir="$MDIR/terraform" destroy "${APPROVE[@]}" "$@"
if [[ -f "$MDIR/teardown.py" ]]; then python3 "$MDIR/teardown.py"; fi
rm -f "$ROOT/.session-${ID^^}"
