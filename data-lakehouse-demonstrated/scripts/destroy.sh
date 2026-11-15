#!/usr/bin/env bash
# ./scripts/destroy.sh C1 | base
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ID="${1:?usage: destroy.sh <base|C1..C7>}"; shift || true
APPROVE=(); [[ "${AUTO_APPROVE:-0}" == "1" ]] && APPROVE=(-auto-approve)
if [[ "$ID" == "base" ]]; then terraform -chdir="$ROOT/base/terraform" destroy "${APPROVE[@]}" "$@"; exit 0; fi
MDIR="$(ls -d "$ROOT"/missions/"${ID^^}"-* 2>/dev/null | head -1)"
if [[ -f "$MDIR/teardown.py" ]]; then python3 "$MDIR/teardown.py" || true; fi
terraform -chdir="$MDIR/terraform" destroy "${APPROVE[@]}" "$@"
