# 002 — Provider Ingestion Implementation Plan

Implements
[`002-provider-ingestion.md`](../specs/002-provider-ingestion.md) after Plan 001.

## Approach

Build a narrow adapter boundary around the normalized input type, then place all
database and lifecycle behavior in an ingestion service. The first production
adapter is intentionally a later change; tests register deterministic fake
adapters.

### Adapter boundary and registry

1. Add an adapter protocol with `provider_key`, `sync_mode`, and
   `iter_jobs() -> AsyncIterator[NormalizedJobInput]`.
2. Add typed adapter exceptions for configuration, authentication, transport,
   rate-limit, upstream schema, and record validation failures. Expose stable
   internal error codes while retaining the original exception only in debug
   logs.
3. Add a registry whose factories receive settings rather than reading global
   environment state. Validate keys and reject duplicate registrations at import
   time.
4. Ship the registry empty of production adapters. Tests inject factories
   directly; do not add a sample provider to production configuration.

### Run storage and ingestion service

1. Add a `SyncRun` SQLAlchemy model and a second Alembic revision with checks and
   indexes for provider/status and recent history.
2. Use a dedicated database connection for `pg_try_advisory_lock`. Derive its
   signed 64-bit key from the first eight bytes of the provider key's SHA-256
   digest in big-endian order, and hold that connection until the run reaches a
   terminal outcome.
3. Commit the running record before network work. Materialize and validate the
   adapter output in memory before opening the job transaction; reject duplicate
   identities within one adapter result.
4. Upsert through SQLAlchemy using the provider identity. Compare normalized
   values explicitly so `updated_at` and the `updated`/`unchanged` counters are
   accurate.
5. Perform full-snapshot deactivation in the same transaction as the upserts,
   scoped strictly to the selected provider and current run's identities.
6. Mark the run succeeded with its final counters in that same transaction, then
   commit the job changes and terminal run state together. On failure, roll back
   that transaction and mark the already-created run failed in a fresh
   transaction. If recording failure also fails, log the run ID and propagate a
   nonzero CLI result.

### Manual command

- Add an ingestion package entry point so `python -m jobs_back.ingestion` works.
- Use `argparse` from the standard library; do not add a CLI framework for one
  command.
- Run the asynchronous fetch with `asyncio.run`, construct database sessions at
  the command boundary, and render the exact exit behavior from the Spec.
- Register no command in `pyproject.toml` until more operational commands justify
  a console-script surface.

## Legacy reuse assessment

Reference project: `job-tracker/backend/src/job_tracker`.

| Legacy code | Disposition | Reason |
| --- | --- | --- |
| `sources/base.py` exception names and small text helpers | Adapt selectively | Framework-independent and tested; align names and validation with the new contract |
| `sources/base.py::SourceJob` | Redesign | Missing employment, structured location, eligibility, lifecycle, and typed compensation fields |
| `sources/adapters.py`, `jsearch.py`, and source fixtures | Defer | Valuable for the concrete-provider batch, but unused by this foundation |
| `ingestion.py` | Reference only | Fetch isolation ideas are useful, but persistence is coupled to SQLite, live search, and deduplication |
| `fetch_runs.py` and its tests | Reference only | Reuse terminal-state and counter scenarios; rewrite for the new schema and transaction contract |
| `cli.py`, `source_usage.py`, and `sync_schedule.py` | Exclude | Carry unrelated commands, quotas, and scheduling outside this batch |

Do not port the legacy `fetch_json` helper until a concrete adapter needs shared
HTTP behavior. This prevents unused retry policy from becoming part of the
foundation accidentally.

## Test plan

- Contract-test registry validation, unknown providers, duplicate keys, and
  injected settings.
- Use fake full-snapshot and incremental adapters to test create, update,
  unchanged, reactivation, and deactivation counts.
- Verify duplicate identities within one result fail before persistence.
- Inject fetch, validation, and database failures and prove job state rolls back
  while the run becomes failed with a sanitized error.
- Run two database-backed sync attempts to prove same-provider lock contention
  and different-provider independence.
- Invoke the module with subprocess tests for exit codes `0`–`3` and stable
  operator output.
- Test interrupted-run observability by leaving a committed running record; do
  not invent automatic recovery until scheduling is designed.

All persistence and advisory-lock tests run against PostgreSQL 16 using the CI
service introduced by Plan 001.

## Completion criteria

- All paired Spec acceptance criteria pass with fake adapters.
- `./ci.sh` and migration upgrade/downgrade pass.
- No concrete provider, scheduler, HTTP sync endpoint, or cross-provider dedup
  code is introduced.
- No runtime import depends on the legacy project.
