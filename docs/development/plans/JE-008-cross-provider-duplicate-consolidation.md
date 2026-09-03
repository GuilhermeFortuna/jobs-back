# JE-008 — Cross-Provider Duplicate Consolidation Implementation Plan

Implements
[`JE-008-cross-provider-duplicate-consolidation.md`](../specs/JE-008-cross-provider-duplicate-consolidation.md)
after JE-007 fan-in delivers results from more than one provider.

## Implementation baseline — reuse, do not rebuild

| Existing work | Current evidence | Disposition |
| --- | --- | --- |
| `search/live.py` | Item accumulation, local filtering, final sort, `resolve_job` | Extend with a consolidation step; do not restructure lifecycle, reuse, or eviction |
| `schemas/discovery.py` | `JobResult`, `SavedJobRead`, `SearchPage` | Extend with `alternate_sources`; keep `extra="forbid"` on request models |
| `models/saved_job.py` | Snapshot columns, unique `(profile_id, provider, provider_job_id)`, check constraints, `ix_saved_jobs_profile_state_saved_at` | Extend with `dedup_key` and `alternate_sources`; retain the existing constraint |
| `alembic/versions/004_add_profiles_and_saved_jobs.py` | Migration style, legacy handling, reversible downgrade | Follow as the pattern for migration `005` |
| `tests/test_migration_004.py` | Migration test harness against a real PostgreSQL database | Follow as the pattern for the `005` migration test |
| `services/profile_library.py` | `save_library_job` resolving through the manager and upserting with `ON CONFLICT DO UPDATE` preserving `applied_at` | Extend the upsert path to consolidate by `dedup_key`; keep the preservation behavior |
| `api/profiles.py` | Save, patch, delete, list routes with 200/201/404/409/410 mapping | Retain routes unchanged; responses carry richer payloads |

JE-004 and JE-005 suites pass today, including `test_library_api.py`,
`test_profiles_api.py`, and `test_migration_004.py`. The JE-004 identity
contract is extended here, not replaced: `(profile_id, provider,
provider_job_id)` remains unique and every existing library assertion must keep
passing.

## Remaining implementation

### Duplicate identity and normalization

1. Add a single normalization module that derives `dedup_key` from company,
   title, and the eligibility discriminator, used by both the search runtime and
   the migration backfill so the two can never drift.
2. Implement the documented normalizations only — case folding, punctuation and
   whitespace collapsing, legal-suffix removal, bracketed and parenthetical
   qualifier removal — and explicitly preserve seniority, discipline, and
   numbering tokens.
3. Build the normalization test table from real observed titles across
   Himalayas, RemoteOK, and Jobicy, including deliberate near-miss pairs that
   must not merge.
4. Keep matching exact on the derived key. Do not introduce edit-distance,
   token-overlap, or embedding similarity, even as an optional path.
5. Treat any input that cannot produce a confident key as unique rather than
   merging it into an existing group.

### Search-time consolidation

1. Insert consolidation into the index between local filtering and the final
   sort, keyed by `dedup_key`, so an item is merged as it arrives rather than in
   a completion sweep.
2. Implement canonical-source selection as a pure comparison — compensation and
   description richness first, then fixed provider precedence — so a later
   arrival can replace the canonical source deterministically.
3. Merge alternate sources without loss, deduplicating repeated
   `(provider, provider_job_id)` pairs, and never drop an `apply_url` or
   `job_url`.
4. Confirm the exact `total` reported at completion is the consolidated count,
   and document that an in-progress count may decrease as duplicates merge.
5. Extend `resolve_job` so resolution by any alternate source identity returns
   the consolidated result, keeping saving authoritative and server-side.
6. Verify consolidation cost stays linear in item count under the existing
   100,000-record benchmark rather than adding a pairwise comparison.

### Library consolidation and migration

1. Persist `dedup_key` and `alternate_sources` on the snapshot, deriving the key
   from the resolved authoritative result rather than from client input.
2. Extend the upsert in `save_library_job` to match on `(profile_id, dedup_key)`
   first, append the incoming source, refresh snapshot fields, and preserve
   `state`, `applied_at`, and `saved_at`.
3. Keep repeated saving a success rather than a conflict, and keep the existing
   200-versus-201 status distinction meaningful for a consolidated save.
4. Write migration `005` adding both columns, backfilling `dedup_key` through
   the shared normalization module, applying the deterministic collision rule,
   then adding the `(profile_id, dedup_key)` unique constraint.
5. Make the downgrade drop the constraint and both columns without attempting to
   restore folded rows, and state that in the migration docstring.
6. Expose `alternate_sources` on library reads so every application link stays
   reachable after a provider removes its listing.

## Test plan

- Normalization unit tables covering every documented rule, real observed titles
  from all three providers, and near-miss pairs that must stay distinct.
- Order-independence tests delivering the same duplicate set in several provider
  arrival orders and asserting an identical canonical choice and identical
  completed pages.
- Consolidation-versus-invariants tests asserting the consolidated exact total,
  unchanged progress and `checked_count` semantics, and unchanged reuse,
  refresh, and eviction behavior.
- Library tests for saving a duplicate from a second provider: one row, appended
  source, preserved `state`, `applied_at`, and `saved_at`, and a success
  response.
- Resolution tests proving an alternate source identity resolves to the same
  authoritative result.
- Migration `005` tests for upgrade, downgrade, backfill correctness, and the
  collision rule folding two pre-existing rows deterministically.
- The 100,000-record benchmark rerun with a high duplicate ratio to prove
  consolidation stays linear.
- OpenAPI tests for `alternate_sources` on search results and library reads.

## Completion criteria

- Every JE-008 acceptance criterion has deterministic automated coverage.
- `./ci.sh lint`, `./ci.sh test`, `uv run alembic upgrade head`, and the `005`
  downgrade all pass against a real PostgreSQL database.
- Runtime and migration derive `dedup_key` from the same module, proven by a
  test that exercises both paths on identical input.
- No fuzzy or semantic matching, cross-profile detection, frontend behavior, or
  persisted provider catalog is added.
