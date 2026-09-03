#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="${SCRIPT_DIR}/docker-compose.yml"
ENV_FILE="${SCRIPT_DIR}/.env"
ENV_EXAMPLE="${SCRIPT_DIR}/.env.example"
PROJECT_NAME="jobs-dev"

if [[ ! -f "${ENV_FILE}" ]]; then
  cp "${ENV_EXAMPLE}" "${ENV_FILE}"
  echo "Created ${ENV_FILE} from .env.example"
fi

# shellcheck disable=SC1090
set -a && source "${ENV_FILE}" && set +a
POSTGRES_HOST_PORT="${POSTGRES_HOST_PORT:-5432}"
POSTGRES_TEST_DB="${POSTGRES_TEST_DB:-jobs_test}"

compose() {
  docker compose \
    --project-name "${PROJECT_NAME}" \
    --env-file "${ENV_FILE}" \
    -f "${COMPOSE_FILE}" \
    "$@"
}

stop_stale_postgres() {
  local stale_containers
  stale_containers="$(docker ps -aq --filter "name=^jobs-back-db-")"
  if [[ -n "${stale_containers}" ]]; then
    echo "Stopping stale jobs-back-db container(s) from the removed compose setup..."
    # shellcheck disable=SC2086
    docker stop ${stale_containers} >/dev/null 2>&1 || true
    # shellcheck disable=SC2086
    docker rm ${stale_containers} >/dev/null 2>&1 || true
  fi
}

ensure_host_port_available() {
  local port="$1"
  local label="$2"
  local occupant
  local project_prefix="${PROJECT_NAME}-"

  occupant="$(
    docker ps --format '{{.Names}}\t{{.Ports}}' \
      | awk -v port=":${port}->" -v prefix="${project_prefix}" '
          $0 ~ port && index($1, prefix) != 1 { print $1; exit }
        '
  )"
  if [[ -n "${occupant}" ]]; then
    echo "Error: host port ${port} is already used by container '${occupant}' (${label})." >&2
    echo "Stop that container or change the port in ${ENV_FILE}." >&2
    exit 1
  fi

  if docker ps --format '{{.Names}}\t{{.Ports}}' | awk -v port=":${port}->" -v prefix="${project_prefix}" '$0 ~ port && index($1, prefix) == 1 { found=1 } END { exit !found }'; then
    return 0
  fi

  if command -v ss >/dev/null 2>&1; then
    if ss -tln | grep -q ":${port} "; then
      echo "Error: host port ${port} is already in use (${label})." >&2
      echo "Change the port in ${ENV_FILE} and update TEST_DATABASE_URL in jobs-back/.env if needed." >&2
      exit 1
    fi
  fi
}

start_postgres() {
  stop_stale_postgres
  ensure_host_port_available "${POSTGRES_HOST_PORT}" "postgres"

  echo "Starting PostgreSQL for local CI (project: ${PROJECT_NAME})..."
  compose up postgres -d --wait

  compose exec -T postgres env POSTGRES_TEST_DB="${POSTGRES_TEST_DB}" \
    bash /docker-entrypoint-initdb.d/10-create-test-db.sh
}

stop_postgres() {
  if compose ps --status running --services postgres 2>/dev/null | grep -qx postgres; then
    echo "Stopping PostgreSQL started for local CI..."
    compose stop postgres
  fi
}

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required to start the local PostgreSQL test database." >&2
  exit 1
fi

case "${1:-up}" in
  up)
    start_postgres
    ;;
  down)
    stop_postgres
    ;;
  *)
    echo "Usage: ensure-postgres.sh [up|down]" >&2
    exit 1
    ;;
esac
