# JE-008 — Cross-Provider Duplicate Consolidation Specification

## Status

Proposed for Batch 03. Depends on JE-007 for multi-provider fan-in and on JE-004
for the personal library contract. Consolidation runs in the in-memory index;
only saved snapshots gain durable fields, so ADR-001 is unchanged.

## Purpose

Collapse the same role, listed on more than one provider, into one search result
and one library row while preserving every original source and application link.
Without consolidation, multi-provider search multiplies the same posting across
boards and the library accumulates duplicate snapshots of one application.

## Duplicate identity

Two normalized results are duplicates when they produce the same `dedup_key`.
The key is derived deterministically from:

| Component | Normalization |
| --- | --- |
| Company | Case-folded, punctuation and whitespace collapsed, common legal suffixes removed (`inc`, `ltd`, `llc`, `gmbh`, `bv`, `sa`, `oy`) |
| Title | Case-folded, punctuation and whitespace collapsed, bracketed and parenthetical qualifiers removed, `(m/f/d)`-style notations removed |
| Eligibility discriminator | Remote type plus a coarse location or eligibility token, so the same title at the same company in two distinct regions stays distinct |

Normalization removes formatting noise only. Seniority words, discipline words,
and numbering are meaningful and are never stripped: `Senior Backend Engineer`
and `Backend Engineer` are distinct roles, as are `Engineer I` and
`Engineer II`. Matching is exact on the derived key. Fuzzy, phonetic, and
semantic similarity are out of scope.

The rule is biased toward false negatives. Showing the same role twice is a
minor annoyance; merging two distinct roles hides an opportunity and corrupts a
saved snapshot, so any ambiguous case must not merge.

## Search-time consolidation

Consolidation happens inside the in-memory index and is applied after
normalization and local filtering and before the final deterministic sort.

- A consolidated result keeps one canonical `provider` and `provider_job_id`
  and carries an `alternate_sources` list.
- Each alternate source entry carries `provider`, `job_url`, and `apply_url`.
  Every original link survives; no source is silently dropped.
- The canonical source is chosen by a stated deterministic rule — richest
  compensation and description data first, then a fixed provider precedence as
  the tiebreak — never by whichever provider's stream arrived first. Because
  JE-007 fan-in is concurrent, the same inputs must always produce the same
  canonical choice.
- Consolidation is incremental. A later-arriving duplicate merges into the
  existing result and may replace the canonical source; it never appends a
  second item.
- Because merging removes items, an in-progress result count may decrease as
  duplicates arrive. `total` remains null until completion, and the exact total
  reported at completion is the consolidated count.
- Progress, `checked_count`, per-provider status, reuse, refresh, and eviction
  semantics from JE-005 and JE-007 are unchanged. `checked_count` counts items
  examined, not items retained.

A consolidated result resolves for saving by its canonical identity. Resolution
by any alternate source identity resolves to the same consolidated result.

## Library consolidation

Saving a job that duplicates a snapshot already held by that profile updates the
existing row instead of creating a second one:

- The existing row's `dedup_key` matches, the incoming source is appended to
  `alternate_sources`, and snapshot fields are refreshed from the incoming
  result.
- `state` and `applied_at` are preserved. A profile that already marked the role
  applied does not silently revert to saved by saving it again from another
  provider.
- `saved_at` is preserved; `updated_at` advances.
- The response reports the existing snapshot, and repeated saving remains a
  success rather than a conflict, matching the JE-004 behavior.
- Library reads expose `alternate_sources` so every application link stays
  reachable, including after a provider removes its listing.

## Migration

Migration `005` extends `saved_jobs`:

| Column | Shape | Meaning |
| --- | --- | --- |
| `dedup_key` | text, not null | Derived duplicate identity for this snapshot |
| `alternate_sources` | JSONB, not null, default `[]` | Additional provider sources for the same role |

The migration backfills `dedup_key` for existing rows using the same derivation
as the runtime. The existing `uq_saved_jobs_profile_provider` constraint remains,
and a unique constraint on `(profile_id, dedup_key)` is added.

Backfilled rows may collide. When two pre-existing rows in one profile derive
the same key, the migration keeps the row with the more advanced state, then the
earlier `saved_at`, folds the other row's identity into its `alternate_sources`,
and deletes it. The collision rule is deterministic and the migration is
reversible: downgrade drops the constraint and both columns and does not attempt
to restore folded rows.

## Out of scope

- Fuzzy, phonetic, or semantic duplicate matching
- AI ranking, resume matching, or semantic search
- Cross-profile or cross-account duplicate detection
- Persisting provider catalogs, search indexes, or consolidation history
- Frontend presentation of sources and consolidated results
- Retroactive merging of library rows beyond the migration backfill

## Acceptance criteria

1. `dedup_key` derivation is deterministic, documented, and identical between
   the runtime and the migration backfill.
2. Results differing only by provider consolidate into one item carrying every
   original source in `alternate_sources`.
3. Roles that differ in seniority, discipline, numbering, or eligibility region
   do not consolidate.
4. The canonical source is identical regardless of the order in which providers
   deliver their batches.
5. Consolidation is applied after local filtering and before the final sort, and
   a completed search reports the consolidated count as its exact `total` while
   JE-005 progress and lifecycle semantics are unchanged.
6. Saving a duplicate of a snapshot already held by a profile updates the
   existing row, appends the new source, and preserves `state`, `applied_at`,
   and `saved_at`.
7. Migration `005` adds both columns, backfills keys, applies the deterministic
   collision rule, enforces `(profile_id, dedup_key)` uniqueness, and downgrades
   cleanly.
8. Resolving a consolidated result by any of its alternate source identities
   returns the same authoritative result.
