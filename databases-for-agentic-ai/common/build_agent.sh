#!/usr/bin/env bash
# Package an agent for AgentCore Runtime direct code deployment (Python 3.12, arm64).
#   build_agent.sh <mission dir>
# - mission has agent/requirements.txt -> its agent/*.py + common/graph/riverbend_graph.py + requirements
# - mission has mcp/requirements.txt   -> its mcp/*.py + requirements
# - otherwise                          -> the shared Trail Desk agent (common/agent/agent.py) + boto3
# Output: <mission dir>/terraform/build/agent.zip
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MDIR="$(cd "${1:?usage: build_agent.sh <mission dir>}" && pwd)"
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
PIP=(python3 -m pip install --quiet --upgrade --target "$WORK/pkg" --platform manylinux2014_aarch64
     --only-binary=:all: --python-version 3.12)
if [[ -f "$MDIR/agent/requirements.txt" ]]; then
  "${PIP[@]}" -r "$MDIR/agent/requirements.txt" >/dev/null
  cp "$MDIR"/agent/*.py "$ROOT/common/graph/riverbend_graph.py" "$WORK/pkg/"
elif [[ -f "$MDIR/mcp/requirements.txt" ]]; then
  "${PIP[@]}" -r "$MDIR/mcp/requirements.txt" >/dev/null
  cp "$MDIR"/mcp/*.py "$WORK/pkg/"
else
  "${PIP[@]}" "boto3>=1.40" >/dev/null
  cp "$ROOT/common/agent/agent.py" "$WORK/pkg/"
fi
mkdir -p "$MDIR/terraform/build"
rm -f "$MDIR/terraform/build/agent.zip"
(cd "$WORK/pkg" && find . -name '__pycache__' -prune -exec rm -rf {} + && rm -rf bin && zip -qr "$MDIR/terraform/build/agent.zip" .)
echo "built $MDIR/terraform/build/agent.zip ($(du -h "$MDIR/terraform/build/agent.zip" | cut -f1))"
