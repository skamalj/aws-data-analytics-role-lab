#!/usr/bin/env bash
# Package common/agent/agent.py + a recent boto3 into <terraform dir>/build/agent.zip
# (AgentCore Runtime direct code deployment, Python, arm64). Pure-Python deps only.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT_DIR="${1:?usage: build_agent.sh <terraform dir>}"
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
python3 -m pip install --quiet --upgrade --target "$WORK/pkg" \
  --platform manylinux2014_aarch64 --only-binary=:all: --python-version 3.12 \
  "boto3>=1.40" >/dev/null
cp "$ROOT/common/agent/agent.py" "$WORK/pkg/"
mkdir -p "$OUT_DIR/build"
rm -f "$OUT_DIR/build/agent.zip"
(cd "$WORK/pkg" && find . -name '__pycache__' -prune -exec rm -rf {} + && zip -qr "$OUT_DIR/build/agent.zip" .)
echo "built $OUT_DIR/build/agent.zip ($(du -h "$OUT_DIR/build/agent.zip" | cut -f1))"
