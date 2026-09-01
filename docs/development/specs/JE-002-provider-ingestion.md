# JE-002 — Provider Ingestion Specification

## Status

Proposed for V1. Depends on the normalized model defined by Spec JE-001.

## Purpose

Provide one provider-neutral way to fetch, validate, and persist job postings.
Provider-specific HTTP and payload rules must not leak into storage, search, or
API code.

## Provider contract

Each adapter exposes:

- a stable `provider_key` matching the job model's provider-key rules;
- a `sync_mode` of `full_snapshot` or `incremental`;
- an asynchronous job iterator that owns upstream pagination and yields validated
  normalized job inputs from Spec JE-001.

The registry maps one key to one adapter factory and rejects duplicate keys.
Selecting an unknown or unconfigured provider fails before a sync run starts.

`full_snapshot` means a successful run represents every currently active job the
provider makes available within that adapter's documented scope. `incremental`
means absence from a run carries no lifecycle meaning.

Adapters must:

- preserve stable provider posting IDs and the complete accepted raw object;
- map provider values to normalized enums explicitly;
- use `unspecified` rather than infer unsupported employment or workplace data;
- produce timezone-aware timestamps;
- validate required fields before yielding a record;
- avoid logging credentials, authorization headers, or complete raw payloads.

Unexpected top-level response shape, a malformed required record, pagination
failure, timeout, or authentication failure fails the provider run. Silently
dropping malformed records is not allowed because it can make a full snapshot
incorrectly deactivate an existing job.

## Sync execution

V1 exposes a manual command:

```text
uv run python -m jobs_back.ingestion sync --provider <provider-key>
```

Exactly one provider is selected per invocation. There is no scheduler and no
HTTP endpoint for starting a sync in this batch.

Execution order is:

1. Resolve configuration and adapter registration.
2. Acquire a provider-scoped PostgreSQL advisory lock without waiting.
3. Commit a `running` sync-run record.
4. Fetch and validate the complete adapter result without modifying jobs.
5. In one database transaction, upsert every identity, apply lifecycle
   transitions, and update the sync run to `succeeded` with final counts.
6. Commit the job changes and terminal run state together.
7. Release the advisory lock in all outcomes.

If fetching or persistence fails, no job changes from that run are committed and
the sync run is marked `failed`. Failure to acquire the lock does not create a
second run; it reports that the provider is already running.

## Upsert and lifecycle rules

For each accepted provider identity:

- create a missing job as active;
- update normalized fields and the latest raw payload;
- preserve `id` and `discovered_at`;
- set `last_seen_at` to the run timestamp;
- clear `inactive_at` and reactivate an inactive job;
- change `updated_at` only when normalized content or lifecycle state changes.

After all upserts in a successful `full_snapshot` run, active jobs for that
provider that were not seen are marked inactive. Incremental runs never infer
inactivity. A failed full snapshot never deactivates jobs.

## Sync-run record

Each started run stores:

- UUID `id`, `provider`, `trigger`, `sync_mode`, and `status`;
- `started_at`, nullable `finished_at`, and nullable sanitized error code/message;
- counts for fetched, created, updated, unchanged, reactivated, and deactivated
  jobs.

`trigger` is `manual` in this batch. Allowed statuses are `running`, `succeeded`,
and `failed`. Counters are non-negative and terminal runs have `finished_at`.
Error messages are operator-facing summaries, not stack traces or upstream
payloads.

## CLI behavior

- Exit `0`: the run succeeded; print its ID and counters.
- Exit `1`: a started run failed; print its ID and sanitized reason.
- Exit `2`: invalid arguments, unknown provider, or missing provider
  configuration; no run was started.
- Exit `3`: the selected provider already has a running process; no run was
  started.

Output is deterministic plain text suitable for local use and shell logs.

## Out of scope

- Concrete provider adapters
- Scheduled or recurring runs
- Multi-provider orchestration
- HTTP-triggered sync and progress streaming
- Cross-provider duplicate consolidation
- Live upstream search
- Background queues and distributed workers
- Provider-specific quota ledgers or retry policies

## Acceptance criteria

1. A fake registered adapter can complete a manual run and persist normalized
   jobs without provider-specific logic in the service.
2. Re-running the same provider identities updates rows without creating
   duplicates or changing public IDs.
3. A successful full snapshot deactivates missing jobs; incremental and failed
   runs do not.
4. Rediscovery reactivates a job and preserves its original discovery timestamp.
5. Fetch or persistence failure leaves all jobs exactly as they were before the
   run and produces a terminal failed run record.
6. Concurrent execution for the same provider is rejected while different
   providers can run independently.
7. CLI exit codes and output distinguish success, run failure, invalid setup,
   and lock contention.
