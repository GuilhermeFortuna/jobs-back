# JE-010 — Profile Skills Implementation Plan

Implements [`JE-010-profile-skills.md`](../specs/JE-010-profile-skills.md) as
the first task of Batch 04, ahead of the JE-011 relevance engine that consumes
the stored skills.

## Implementation baseline — reuse, do not rebuild

| Existing work | Current evidence | Disposition |
| --- | --- | --- |
| `models/profile.py` | `Profile` with `preferences` JSONB, name check constraint, timestamps | Add a `skills` JSONB column; do not restructure the model or touch `preferences` |
| `alembic/versions/005_add_saved_job_dedup.py` | Migration style, reversible downgrade, docstring conventions | Follow as the pattern for migration `006` |
| `tests/test_migration_004.py` | Migration harness against a real PostgreSQL database | Follow as the pattern for the `006` migration test |
| `schemas/discovery.py` | `ProfileCreate`, `ProfilePatch`, `ProfileRead`, `extra="forbid"` on request models | Extend with a `Skill` model and `skills` fields; keep `extra="forbid"` |
| `api/profiles.py` | Create, get, patch, list routes with 404/409/422 mapping | Extend existing handlers; add no route |
| `search/live.py` | `filter_key`, `states`, `latest`, `refreshing`, eviction pass | Add a narrowly scoped per-profile discard entry point; do not alter lifecycle |
| `search/relevance.py` | Delivered by JE-011 | Shared normalizer — JE-010 lands the normalizer module and JE-011 builds scoring on it |

JE-004's profile suites pass today. This task extends that contract; every
existing profile assertion must keep passing.

## Sequencing note

The normalizer is shared by JE-010 (deriving stored tokens) and JE-011 (matching
against job text). This task creates `search/relevance.py` containing the
normalizer and alias table only. JE-011 adds scoring to the same module. Neither
task may introduce a second normalization implementation.

## Remaining implementation

### Normalizer

1. Create `search/relevance.py` with a single `normalize_token` entry point:
   case fold, strip punctuation and separators, collapse whitespace, apply the
   alias table, return the token or an empty string.
2. Declare the alias table as module-level data, keyed normalized-to-normalized,
   deliberately small and documented as curated rather than exhaustive.
3. Cover the normalizer with a unit table before any caller exists.

### Persistence

1. Add the `skills` column to `Profile` with a not-null JSONB default of `[]`.
2. Write migration `006` adding the column with a server default, and a
   downgrade that drops it; state in the docstring that the downgrade discards
   stored skills.
3. Do not backfill: existing profiles start with an empty list.

### Contract

1. Add a `Skill` schema with `label` and server-derived `token`, and attach
   `skills` to `ProfileRead`, `ProfileCreate`, and `ProfilePatch`.
2. Accept labels only on write. Derive tokens server-side and reject any
   client-supplied token through the existing `extra="forbid"` behavior.
3. Enforce the count cap, label length, empty-token rejection, and duplicate
   rejection in one validator so create and patch cannot diverge. A duplicate is
   a 422 naming both labels and the shared token, never a silent fold.
4. Treat a present `skills` list on patch as a wholesale replacement and an
   absent field as no change.

### Cache invalidation

1. Add a `discard_profile_searches(profile_id)` method to `LiveSearchManager`
   that drops that profile's entries from `states`, `latest`, and `refreshing`,
   cancelling in-flight tasks for those states only.
2. Call it from the profile patch path only when the stored skills actually
   changed, comparing normalized stored form rather than request payloads.
3. Prove by test that another profile's warm index, in-flight refresh, and
   eviction schedule are untouched.

## Test plan

- Normalizer unit table: casing, punctuation, dotted forms, alias hits, inputs
  that normalize to empty.
- Migration `006` upgrade and downgrade against a real PostgreSQL database,
  including an existing profile row defaulting to `[]`.
- Profile API round-trip tests for create, patch, read, and list preserving
  label text and order.
- Validation tests for each rule returning 422 with no write performed.
- A test that a client-supplied `token` is rejected.
- Invalidation tests: skills change discards the owning profile's states; an
  unchanged patch discards nothing; a second profile's warm state survives.
- Re-run of JE-004, JE-005, JE-007, and JE-008 suites unchanged.

## Completion criteria

- Every JE-010 acceptance criterion has deterministic automated coverage.
- `./ci.sh lint`, `./ci.sh test`, `uv run alembic upgrade head`, and the `006`
  downgrade pass against a real PostgreSQL database.
- Exactly one normalization implementation exists in the codebase.
- No scoring, no filter change, no frontend change, and no new route is added.
