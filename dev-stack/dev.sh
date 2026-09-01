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
