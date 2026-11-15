#!/usr/bin/env bash
# Mock exam mode - see scripts/exam.py.   ./scripts/exam.sh start | status | grade | end
set -euo pipefail
cd "$(dirname "$0")/.."
exec python3 scripts/exam.py "$@"
