#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CI_STARTED_POSTGRES=0

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

should_skip_db_bootstrap() {
  [[ "${CI_SKIP_DB_BOOTSTRAP:-}" == "1" || "${GITHUB_ACTIONS:-}" == "true" ]]
}

is_local_test_database_url() {
  local url="$1"
  [[ "${url}" =~ @([^:/]+) ]] || return 1
  case "${BASH_REMATCH[1]}" in
    localhost | 127.0.0.1) return 0 ;;
    *) return 1 ;;
  esac
}

test_database_is_reachable() {
  DATABASE_URL="${TEST_DATABASE_URL}" uv run python - <<'PY'
import os
import sys

from sqlalchemy import create_engine, text

try:
    with create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True).connect() as conn:
        conn.execute(text("SELECT 1"))
except Exception:
    sys.exit(1)
PY
}

stop_test_database() {
  if [[ "${CI_STARTED_POSTGRES}" != "1" ]]; then
    return
  fi

  echo "==> postgres down"
  "${SCRIPT_DIR}/dev-stack/ensure-postgres.sh" down
}

ensure_test_database() {
  if should_skip_db_bootstrap || test_database_is_reachable; then
    return
  fi

  if ! is_local_test_database_url "${TEST_DATABASE_URL}"; then
    echo "TEST_DATABASE_URL is not reachable and does not point to localhost." >&2
    echo "Start the database yourself or point TEST_DATABASE_URL at a running instance." >&2
    exit 1
  fi

  echo "==> postgres"
  "${SCRIPT_DIR}/dev-stack/ensure-postgres.sh" up
  CI_STARTED_POSTGRES=1

  if ! test_database_is_reachable; then
    echo "PostgreSQL test database is still unreachable after bootstrap." >&2
    exit 1
  fi
}

run_test() {
  trap stop_test_database EXIT INT TERM

  load_test_database_url
  if [[ -z "${TEST_DATABASE_URL:-}" ]]; then
    echo "TEST_DATABASE_URL is required for the full PostgreSQL test suite." >&2
    echo "It must point to a disposable database whose name contains 'test'." >&2
    exit 1
  fi
  ensure_test_database
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
