# Job Engine API (`jobs-back`)

Python backend for discovering and browsing job openings aggregated from multiple providers.

See the product north star: [docs/job-engine-v1-goal.md](docs/job-engine-v1-goal.md).

## Stack

- Python 3.12 + [uv](https://docs.astral.sh/uv/)
- FastAPI, SQLAlchemy 2, Alembic, PostgreSQL 16
- Ruff (lint), pytest

This repo is scaffold-only so far: health endpoint, DB wiring, and migrations tooling — no Job model or provider adapters yet.

## Prerequisites

- [uv](https://docs.astral.sh/uv/)
- Docker (for local Postgres)

## Local setup

```bash
cp .env.example .env
docker compose up -d
uv sync --group dev
```

### Run the API

```bash
uv run uvicorn jobs_back.main:app --reload --port 8000
```

Health check: `curl http://localhost:8000/health` → `{"status":"ok"}`

### Lint and test

```bash
uv run ruff check src tests alembic
uv run pytest
```

### Migrations

Alembic is configured against `Base.metadata` and `DATABASE_URL`. There are no domain models yet; create the first revision when the Job schema lands:

```bash
uv run alembic revision --autogenerate -m "add jobs"
uv run alembic upgrade head
```

## Cross-repo workflow

With [jobs-front](../jobs-front) alongside this repo:

1. `docker compose up -d` (this repo)
2. Copy `.env.example` → `.env` in both repos
3. Backend: `uv sync --group dev && uv run uvicorn jobs_back.main:app --reload --port 8000`
4. Frontend: `pnpm install && pnpm dev` (port 3000)
5. Open `http://localhost:3000` and confirm `http://localhost:8000/health`

## What's next

- Normalized Job model and Alembic migration
- Provider adapter interface
- Search / filter API
- Deduplication
