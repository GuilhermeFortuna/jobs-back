#!/usr/bin/env bash
set -euo pipefail

cd /app
uv sync --group dev

exec "$@"
