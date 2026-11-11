# Shared bash helpers for solution scripts.  Source it:  . "$ROOT/common/lib.sh"
set -euo pipefail

# stack_output <stack> <OutputKey>
stack_output() {
  aws cloudformation describe-stacks --stack-name "$1" \
    --query "Stacks[0].Outputs[?OutputKey=='$2'].OutputValue" --output text
}

# wait_crawler <crawler-name> : start it and block until it is READY again
run_crawler() {
  local name="$1"
  aws glue start-crawler --name "$name"
  echo -n ">> crawler $name running"
  sleep 10
  while [[ "$(aws glue get-crawler --name "$name" --query Crawler.State --output text)" != "READY" ]]; do
    echo -n "."; sleep 10
  done
  echo " $(aws glue get-crawler --name "$name" --query Crawler.LastCrawl.Status --output text)"
}

# athena <workgroup> <sql-file|-e sql>
athena() {
  local wg="$1"; shift
  if [[ "$1" == "-e" ]]; then
    python3 "$ROOT/common/athena_run.py" --workgroup "$wg" --sql "$2" "${@:3}"
  else
    python3 "$ROOT/common/athena_run.py" --workgroup "$wg" --file "$1" "${@:2}"
  fi
}

# quietly ignore "not found" style errors during cleanup
try() { "$@" >/dev/null 2>&1 || true; }
