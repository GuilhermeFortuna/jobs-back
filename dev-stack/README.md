# Local development stack

Docker Compose orchestration for the full Job Engine stack: **frontend**, **backend**, and **PostgreSQL**.

## Quick start

From the workspace root (`jobs/`, parent of `jobs-back` and `jobs-front`):

```bash
./dev.sh
```

First run copies `dev-stack/.env.example` → `dev-stack/.env` if missing.

Or run directly from this directory:

```bash
./dev.sh
```

## Services

| Service | Image / build | Host port (default) | Internal |
|---------|---------------|---------------------|----------|
| frontend | `jobs-front/Dockerfile.dev` | 3000 | `frontend:3000` |
| backend | `jobs-back/Dockerfile.dev` | 8000 | `backend:8000` |
| postgres | `postgres:16` | 5432 | `postgres:5432` |

Verify:

```bash
curl http://localhost:8000/health   # {"status":"ok"}
# Frontend: http://localhost:3000
```

Press **Ctrl+C** to stop. Containers and networks are removed; database data in the `jobs_pg_data` volume persists.

## Configuration

Copy and edit `dev-stack/.env` (or let `dev.sh` create it on first run):

| Variable | Default | Description |
|----------|---------|-------------|
| `FRONTEND_PORT` | `3000` | Host port for Next.js dev server |
| `BACKEND_PORT` | `8000` | Host port for FastAPI / uvicorn |
| `POSTGRES_HOST_PORT` | `5432` | Host port for PostgreSQL |
| `POSTGRES_TEST_DB` | `jobs_test` | Disposable database used by backend tests |

`CORS_ORIGINS` and `NEXT_PUBLIC_API_URL` are derived from these ports in `docker-compose.yml` so browser and API URLs stay aligned.

## Networking

- **Backend → Postgres:** `postgresql+psycopg://jobs:jobs@postgres:5432/jobs` (Docker service name)
- **Host tests → Postgres:** `postgresql+psycopg://jobs:jobs@localhost:5432/jobs_test`
- **Browser → API:** `http://localhost:${BACKEND_PORT}` (`NEXT_PUBLIC_API_URL`)
- **Browser → UI:** `http://localhost:${FRONTEND_PORT}`

Postgres is exposed so host-side CI and Git hooks can reach the isolated test
database. Change `POSTGRES_HOST_PORT` and the matching URLs in `jobs-back/.env` if
port 5432 is already occupied.

## Volumes

| Volume | Purpose |
|--------|---------|
| `jobs_pg_data` | PostgreSQL data (persistent) |
| `backend_venv` | Python virtualenv inside backend container |
| `frontend_node_modules` | `node_modules` isolated from host |
| `frontend_next` | Next.js build cache isolated from host |

Source code is bind-mounted from `jobs-back` and `jobs-front` for hot reload.

## Troubleshooting

**Rebuild images** after Dockerfile or lockfile changes — `dev.sh` runs `up --build` automatically.

**Reset dependency volumes** (not database):

```bash
docker compose --project-name jobs-dev --env-file dev-stack/.env -f dev-stack/docker-compose.yml down
docker volume rm jobs-dev_backend_venv jobs-dev_frontend_node_modules jobs-dev_frontend_next
```

**Reset database** (destructive):

```bash
docker volume rm jobs-dev_jobs_pg_data
```

**Stale Postgres from old compose:** The previous `jobs-back/docker-compose.yml` used project name `jobs-back` and container `jobs-back-db-1`. `dev.sh` stops that container automatically before starting. Data lives in volume `jobs-back_jobs_pg_data`; the dev stack uses `jobs-dev_jobs_pg_data`.

## Single-process live search

The backend keeps progressive search state **in memory in one process**. Use a
single Uvicorn worker for local dev and production until distributed search is
implemented. Multiple workers or replicas will not share search IDs. See
[`jobs-back/README.md`](../README.md#live-search-je-005) for `SEARCH_*` and
Himalayas env vars.
