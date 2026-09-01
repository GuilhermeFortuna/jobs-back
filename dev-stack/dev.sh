#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "${SCRIPT_DIR}/../../" && pwd)"
COMPOSE_FILE="${SCRIPT_DIR}/docker-compose.yml"
ENV_FILE="${SCRIPT_DIR}/.env"
ENV_EXAMPLE="${SCRIPT_DIR}/.env.example"
BACKEND_ENV_FILE="${WORKSPACE_ROOT}/jobs-back/.env"
BACKEND_ENV_EXAMPLE="${WORKSPACE_ROOT}/jobs-back/.env.example"
PROJECT_NAME="jobs-dev"

if [[ ! -f "${ENV_FILE}" ]]; then
  cp "${ENV_EXAMPLE}" "${ENV_FILE}"
  echo "Created ${ENV_FILE} from .env.example"
fi

if [[ ! -f "${BACKEND_ENV_FILE}" ]]; then
  cp "${BACKEND_ENV_EXAMPLE}" "${BACKEND_ENV_FILE}"
  echo "Created ${BACKEND_ENV_FILE} from .env.example"
fi

# shellcheck disable=SC1090
set -a && source "${ENV_FILE}" && set +a
POSTGRES_HOST_PORT="${POSTGRES_HOST_PORT:-5432}"

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

  # Only check non-Docker listeners when this project's stack is not already bound.
  if docker ps --format '{{.Names}}\t{{.Ports}}' | awk -v port=":${port}->" -v prefix="${project_prefix}" '$0 ~ port && index($1, prefix) == 1 { found=1 } END { exit !found }'; then
    return 0
  fi

  if command -v ss >/dev/null 2>&1; then
    if ss -tln | grep -q ":${port} "; then
      echo "Error: host port ${port} is already in use (${label})." >&2
      echo "Change the port in ${ENV_FILE} and update DATABASE_URL in ${BACKEND_ENV_FILE} if needed." >&2
      exit 1
    fi
  fi
}

stop_stale_postgres
ensure_host_port_available "${POSTGRES_HOST_PORT}" "postgres"

cd "${WORKSPACE_ROOT}"

cleanup() {
  docker compose \
    --project-name "${PROJECT_NAME}" \
    --env-file "${ENV_FILE}" \
    -f "${COMPOSE_FILE}" \
    down --remove-orphans
}

trap cleanup EXIT INT TERM

docker compose \
  --project-name "${PROJECT_NAME}" \
  --env-file "${ENV_FILE}" \
  -f "${COMPOSE_FILE}" \
  up --build
