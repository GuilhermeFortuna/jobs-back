#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'EOF'
Usage: ./ci.sh [command]

Commands:
  all   Run the full CI suite (default)
  lint  Run Ruff
  test  Run pytest
EOF
}

run_lint() {
  echo "==> lint"
  uv run ruff check src tests alembic
}

run_test() {
  echo "==> test"
  uv run pytest
}

run_all() {
  run_lint
  run_test
}

cmd="${1:-all}"

case "$cmd" in
  all)
    run_all
    ;;
  lint)
    run_lint
    ;;
  test)
    run_test
    ;;
  *)
    usage
    exit 1
    ;;
esac
