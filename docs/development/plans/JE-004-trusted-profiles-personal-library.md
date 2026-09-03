# JE-004 — Trusted Profiles and Personal Job Library Implementation Plan

Implements
[`JE-004-trusted-profiles-personal-library.md`](../specs/JE-004-trusted-profiles-personal-library.md).

## Implementation baseline — reuse, do not rebuild

Implementation started before this plan was recorded. Workers must inspect and
improve these files rather than create parallel replacements.

| Existing work | Current evidence | Disposition |
| --- | --- | --- |
| `models/profile.py` | Profile UUID, unique display name, JSONB preferences, timestamps | Retain; verify constraints and relationship behavior |
| `models/saved_job.py` | Profile-scoped provider identity, saved/applied state, normalized snapshot columns | Retain; correct snapshot/FK/timestamp details as tests require |
| Alembic revision `004_add_profiles_and_saved_jobs.py` | Upgrades successfully on the local PostgreSQL development DB | Extend: it currently adds tables but does not retire/refuse nonempty legacy catalog data |
| `schemas/discovery.py` | Profile and library request/response schemas exist | Retain; split if clarity improves and align save input with authoritative search identity |
| `api/profiles.py` | Profile CRUD subset and library list/create/patch/delete exist | Retain; add missing job GET, isolation/idempotency, and exact error semantics |
| Frontend API and workspace | Calls profile and library endpoints | Coordinate contract changes with JE-006; do not preserve incorrect payloads for compatibility |

This baseline has passed Ruff, but it has no JE-004-specific automated tests and
is not accepted.

## Remaining implementation

### Model and migration

1. Decide the final snapshot column set from the Spec, including how the
   accepted provider payload is retained internally but omitted publicly.
2. Add or correct database constraints for trimmed names, provider identity,
   state, `applied_at`, positive/order-valid salary values, and update indexes
   used by profile/state library lists.
3. Extend revision 004 to inspect legacy `jobs` and `sync_runs`. Abort with a
   clear operator message when either is nonempty; remove empty legacy catalog
   tables and indexes so the active database contains only durable personal
   state.
4. Make upgrade/downgrade deterministic from base and from revision 003. Do not
   silently mutate or delete nonempty user data in tests or development.
5. Update test cleanup fixtures for the final table set without weakening the
   dedicated-test-database guard.

### Service and API

1. Move profile/library business rules from route functions into a small service
   layer so isolation and state transitions can be tested without HTTP details.
2. Add `GET /profiles/{profile_id}/jobs/{job_id}` and ensure every read/write
   constrains both IDs.
3. Change library creation to resolve `search_id` plus provider identity through
   JE-005. Copy normalized data and internal raw payload server-side.
4. Implement the unique identity as an idempotent create/update operation.
   Handle concurrent inserts without returning a misleading duplicate error.
5. Preserve `applied_at` on repeated applied writes, clear it on saved, and
   update state timestamps only when meaningful state changes occur.
6. Define exact `404`, `409`, `410`, and `422` responses in OpenAPI. Never expose
   provider payload data.

## Test plan

- Migration from revision 003 with empty legacy tables succeeds and removes the
  catalog; nonempty jobs or sync runs refuse without losing rows.
- Profile create/list/get/patch covers trimming, duplicate names, invalid
  preferences, missing IDs, and timestamp behavior.
- Two profiles with the same provider identity receive distinct snapshots and
  cannot access, update, or delete each other's rows.
- Repeated and concurrent saves remain one row.
- Saved → applied → applied → saved transitions enforce timestamp semantics.
- Either state deletes permanently; an unknown or cross-profile UUID is `404`.
- Search-derived snapshot tests prove persistence survives JE-005 cache eviction
  and raw payload never appears in public JSON.

## Completion criteria

- Every JE-004 acceptance criterion has a PostgreSQL API-level test.
- Revision upgrade/downgrade and the explicit legacy-data refusal test pass.
- The backend test suite passes after obsolete Batch 01 runtime tests are moved
  to historical coverage or replaced by Batch 02 contract tests; do not merely
  delete failing tests without recording the supersession.
- OpenAPI matches the final profile/library contract.

