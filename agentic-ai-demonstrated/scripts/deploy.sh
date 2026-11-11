#!/usr/bin/env bash
# Build the agent package and apply a mission's Terraform.
#   ./scripts/deploy.sh M1                 (interactive approval)
#   AUTO_APPROVE=1 ./scripts/deploy.sh M3
#   ./scripts/deploy.sh M2 -var region=us-east-1
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ID="${1:?usage: deploy.sh <M1..M6> [terraform args]}"; shift
DIR="$(ls -d "$ROOT"/missions/"${ID^^}"-*/terraform 2>/dev/null | head -1)"
[[ -n "$DIR" ]] || { echo "no mission $ID"; exit 1; }
"$ROOT/common/build_agent.sh" "$DIR"
[[ -x "$DIR/../build_extra.sh" ]] && "$DIR/../build_extra.sh" "$DIR"
terraform -chdir="$DIR" init -input=false -upgrade >/dev/null
APPROVE=(); [[ "${AUTO_APPROVE:-0}" == "1" ]] && APPROVE=(-auto-approve)
terraform -chdir="$DIR" apply "${APPROVE[@]}" "$@"
echo ">> Deployed ${ID^^}. Read missions/$(basename "$(dirname "$DIR")")/README.md, then:"
echo "   python3 common/chat.py ${ID^^} \"<your question>\""
