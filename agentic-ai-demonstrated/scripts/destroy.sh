#!/usr/bin/env bash
# Tear a mission down completely.   ./scripts/destroy.sh M1
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ID="${1:?usage: destroy.sh <M1..M6>}"; shift || true
DIR="$(ls -d "$ROOT"/missions/"${ID^^}"-*/terraform 2>/dev/null | head -1)"
[[ -n "$DIR" ]] || { echo "no mission $ID"; exit 1; }
[[ -f "$DIR/build/agent.zip" ]] || "$ROOT/common/build_agent.sh" "$DIR"   # plan needs the file to exist
[[ -x "$DIR/../build_extra.sh" ]] && "$DIR/../build_extra.sh" "$DIR"
APPROVE=(); [[ "${AUTO_APPROVE:-0}" == "1" ]] && APPROVE=(-auto-approve)
terraform -chdir="$DIR" destroy "${APPROVE[@]}" "$@"
rm -f "$ROOT/.session-${ID^^}"
