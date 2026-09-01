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

load_test_database_url() {
  if [[ -n "${TEST_DATABASE_URL:-}" || ! -f .env ]]; then
    return
  fi

  local configured_url
  configured_url="$(sed -n 's/^TEST_DATABASE_URL=//p' .env | tail -n 1)"
  configured_url="${configured_url%$'\r'}"
  if [[ -n "${configured_url}" ]]; then
    export TEST_DATABASE_URL="${configured_url}"
  fi
}

run_test() {
  load_test_database_url
  if [[ -z "${TEST_DATABASE_URL:-}" ]]; then
    echo "TEST_DATABASE_URL is required for the full PostgreSQL test suite." >&2
    echo "It must point to a disposable database whose name contains 'test'." >&2
    exit 1
  fi
  echo "==> schema"
  DATABASE_URL="${TEST_DATABASE_URL}" uv run python - <<'PY'
from sqlalchemy import create_engine, inspect, text

from alembic import command
from alembic.config import Config

url = __import__("os").environ["DATABASE_URL"]
engine = create_engine(url)
inspector = inspect(engine)
if "jobs" in inspector.get_table_names():
    with engine.begin() as connection:
        if connection.execute(text("SELECT COUNT(*) FROM jobs")).scalar():
            connection.execute(text("DELETE FROM jobs"))

cfg = Config("alembic.ini")
cfg.set_main_option("sqlalchemy.url", url)
command.upgrade(cfg, "head")
engine.dispose()
PY
  DATABASE_URL="${TEST_DATABASE_URL}" uv run alembic check
  echo "==> test"
  DATABASE_URL="${TEST_DATABASE_URL}" uv run pytest
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
