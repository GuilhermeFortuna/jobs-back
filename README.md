# Job Engine API (`jobs-back`)

Python backend for discovering and browsing job openings aggregated from multiple providers.

See the product north star: [docs/job-engine-v1-goal.md](docs/job-engine-v1-goal.md).

## Stack

- Python 3.12 + [uv](https://docs.astral.sh/uv/)
- FastAPI, SQLAlchemy 2, Alembic, PostgreSQL 16
- Ruff (lint), pytest

This repo is scaffold-only so far: health endpoint, DB wiring, and migrations tooling — no Job model or provider adapters yet.

## Prerequisites

**Containerized dev (recommended):** Docker and Docker Compose only.

**Local dev (optional):** [uv](https://docs.astral.sh/uv/) and Docker (for Postgres if not using the full stack).

## Local setup (Docker)

With [jobs-front](../jobs-front) as a sibling directory, from the workspace root (`jobs/`):

```bash
./dev.sh
```

This starts frontend, backend, and PostgreSQL with hot reload. See [dev-stack/README.md](dev-stack/README.md) for ports, env vars, and troubleshooting.

First-time setup copies `dev-stack/.env.example` → `dev-stack/.env` automatically.

Health check: `curl http://localhost:8000/health` → `{"status":"ok"}`

## Local setup (without Docker for the API)

If you prefer running uvicorn on the host (e.g. IDE debugging):

```bash
cp .env.example .env
./dev-stack/dev.sh   # or: docker compose from dev-stack for postgres only
uv sync --group dev
uv run uvicorn jobs_back.main:app --reload --port 8000
```

For Postgres only via Compose:

```bash
docker compose --project-name jobs-dev --env-file dev-stack/.env -f dev-stack/docker-compose.yml up postgres -d
```

Set `DATABASE_URL=postgresql+psycopg://jobs:jobs@localhost:5432/jobs` in `.env` when Postgres is exposed on the host.

### CI

Run the same validation as GitHub Actions (requires `uv sync --group dev` first):

```bash
./ci.sh          # full suite
./ci.sh lint
./ci.sh test
```

### Git hooks

Install and register commit + push hooks (included in dev dependencies):

```bash
uv sync --group dev
uv run pre-commit install --hook-type pre-commit --hook-type pre-push
```

Hook behavior:

- **pre-commit**: `ruff format` and `ruff check --fix` on staged Python files
- **pre-push**: `./ci.sh` (full CI suite)

Run hooks manually:

```bash
uv run pre-commit run --all-files
uv run pre-commit run --hook-stage pre-push --all-files
```

### Migrations

Alembic is configured against `Base.metadata` and `DATABASE_URL`. There are no domain models yet; create the first revision when the Job schema lands:

```bash
uv run alembic revision --autogenerate -m "add jobs"
uv run alembic upgrade head
```

## Cross-repo workflow

With [jobs-front](../jobs-front) alongside this repo:

1. From workspace root: `./dev.sh`
2. Open `http://localhost:3000` and confirm `http://localhost:8000/health`

Port overrides: edit `dev-stack/.env` (`FRONTEND_PORT`, `BACKEND_PORT`).

## What's next

- Normalized Job model and Alembic migration
- Provider adapter interface
- Search / filter API
- Deduplication
