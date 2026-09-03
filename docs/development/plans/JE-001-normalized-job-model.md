# JE-001 — Normalized Job Model Implementation Plan

Implements
[`JE-001-normalized-job-model.md`](../specs/JE-001-normalized-job-model.md).

## Approach

Add the first domain model and Alembic revision on the existing SQLAlchemy
`Base`. Keep normalization as pure functions so adapters, migrations, and tests
use one set of rules.

### Domain and persistence

1. Add Python string enums for remote type, employment type, salary period, and
   lifecycle status. Persist enum values as constrained strings rather than
   PostgreSQL enum types so later value additions do not require enum DDL.
2. Add a `Job` SQLAlchemy model using PostgreSQL UUID, `NUMERIC(14, 2)`, JSONB,
   timezone-aware timestamps, and a nullable array for eligibility countries.
3. Generate UUIDs in the application and use UTC application timestamps. Keep
   database defaults for `discovered_at`, `last_seen_at`, and `updated_at` as a
   safety net.
4. Import the model from the model package before Alembic reads `Base.metadata`.
5. Create an Alembic revision with:
   - the `jobs` table and provider-identity unique constraint;
   - checks for non-empty required strings, salary positivity, range ordering,
     and lifecycle timestamp consistency;
   - B-tree indexes on `(status, posted_at, id)` and `(provider, status)`;
   - a GIN index on `eligible_country_codes`.
6. Add provider-neutral input validation and pure compensation annualization.
   Quantize accepted amounts to two decimal places using `Decimal` and reject
   booleans, non-finite values, zero, and negative values.

The search-specific full-text index is added with the search API work, when its
query expression is fixed.

### Public and internal types

- Define one validated internal job-input type for ingestion. Do not use the ORM
  object as adapter input.
- Define reusable job summary/detail response types, but do not expose routes in
  this change. The search API Plan finalizes and wires those schemas.
- Keep `raw_payload` off response types by construction rather than filtering it
  at serialization time.

## Legacy reuse assessment

Reference project: `job-tracker/backend/src/job_tracker`.

| Legacy code | Disposition | Reason |
| --- | --- | --- |
| `salary.py` period aliases/multipliers | Adapt | Pure, tested business rules; change float output to `Decimal` and remove periodless-value guessing |
| `tests/test_salary.py` | Adapt | Retain recognized-period, invalid-number, and unknown-period cases; update the new contract |
| `sources/base.py::stated_compensation` | Reference | Useful input cases, but the new validated input owns compensation parsing |
| SQLite migrations and `store.py` | Exclude | Incompatible with SQLAlchemy, PostgreSQL types, Alembic, and centralized concurrency |
| `normalization.py` and `deduplication.py` | Exclude | They exist primarily for cross-provider collapse, which this batch explicitly defers |

Do not copy a legacy file wholesale. Port the small period table and applicable
test cases into the new package structure; implement the remainder against this
specification.

## Test plan

- Unit-test every enum and required-string validation boundary.
- Parameterize compensation tests for hourly, daily, weekly, monthly, yearly,
  other, missing period, invalid decimal, and one-sided ranges.
- Verify ISO normalization, eligibility null/empty/list semantics, sorting, and
  duplicate removal.
- Run migration upgrade on an empty PostgreSQL database and inspect all columns,
  constraints, and indexes.
- Test provider-identity uniqueness and every database check with real
  PostgreSQL; SQLite is not an acceptable substitute.
- Round-trip a fully populated and a minimum viable `Job` through SQLAlchemy.
- Verify response serialization cannot include `raw_payload`.

Add PostgreSQL 16 as a GitHub Actions service and a dedicated test database URL
before enabling database integration tests in `./ci.sh`.

## Completion criteria

- All acceptance criteria in the paired Spec have an automated test.
- `uv run alembic upgrade head`, `./ci.sh lint`, and `./ci.sh test` pass from a
  clean database.
- Downgrading the new revision removes only objects introduced by this Plan.
- No source-provider, deduplication, or API route behavior is introduced.
