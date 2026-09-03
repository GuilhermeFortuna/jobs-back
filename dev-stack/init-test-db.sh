#!/usr/bin/env bash
set -euo pipefail

test_database="${POSTGRES_TEST_DB:-jobs_test}"

if [[ ! "${test_database}" =~ ^[A-Za-z0-9_]+$ ]]; then
  echo "POSTGRES_TEST_DB must contain only letters, digits, and underscores." >&2
  exit 1
fi

exists="$({
  psql \
    --username "${POSTGRES_USER}" \
    --dbname "${POSTGRES_DB}" \
    --tuples-only \
    --no-align \
    --command "SELECT 1 FROM pg_database WHERE datname = '${test_database}'"
} | tr -d '[:space:]')"

if [[ "${exists}" != "1" ]]; then
  createdb --username "${POSTGRES_USER}" "${test_database}"
fi
