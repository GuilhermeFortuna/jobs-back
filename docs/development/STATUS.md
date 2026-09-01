# Specification + Plan status

This file is the single source of truth for the implementation status of every
Spec + Plan pair. A row tracks the deliverable governed by the pair, not whether
the two Markdown files exist.

Status values:

- `DRAFT` — the Spec or Plan is not yet decision-complete.
- `READY` — the pair is decision-complete and all dependencies are done.
- `IN PROGRESS` — implementation has started but does not meet completion
  criteria yet.
- `DONE` — the Plan's completion criteria and the Spec's acceptance criteria are
  satisfied.
- `BLOCKED` — implementation cannot start or finish until the listed dependency
  or an explicitly recorded external condition is resolved.

## Batches

**01 — Backend foundation.** Normalized PostgreSQL model, provider-neutral
ingestion path, and searchable read API. Defers concrete providers, scheduling,
frontend discovery, and cross-provider deduplication. Catalog-persistence runtime
is superseded by
[ADR-001](decisions/ADR-001-personal-library-live-search.md); completion status
is unchanged.

**02 — Personalized live job search.** Trusted profiles, live provider results,
and durable saved/applied snapshots only. JE-005 and JE-006 have partial
implementation; their Plans contain reuse ledgers so worker agents finish that
work instead of rebuilding it.

## Tasks

| ID | Batch | Status | Depends on | Deliverable |
| --- | --- | --- | --- | --- |
| [JE-001](specs/JE-001-normalized-job-model.md) / [Plan](plans/JE-001-normalized-job-model.md) | 01 | `DONE` | None | Normalized PostgreSQL job model, validation, migration, and lifecycle fields |
| [JE-002](specs/JE-002-provider-ingestion.md) / [Plan](plans/JE-002-provider-ingestion.md) | 01 | `DONE` | JE-001 | Provider adapter contract, atomic ingestion service, sync-run tracking, and manual runner |
| [JE-003](specs/JE-003-job-search-api.md) / [Plan](plans/JE-003-job-search-api.md) | 01 | `DONE` | JE-001 | Filtered and deterministically sorted job list and detail API |
| [JE-004](specs/JE-004-trusted-profiles-personal-library.md) / [Plan](plans/JE-004-trusted-profiles-personal-library.md) | 02 | `DONE` | None | Trusted profiles, default preferences, and isolated saved/applied snapshots |
| [JE-005](specs/JE-005-live-provider-search-himalayas.md) / [Plan](plans/JE-005-live-provider-search-himalayas.md) | 02 | `IN PROGRESS` | JE-004 | Per-profile progressive in-memory search and hardened Himalayas adapter |
| [JE-006](specs/JE-006-personal-job-discovery-frontend.md) / [Plan](plans/JE-006-personal-job-discovery-frontend.md) | 02 | `IN PROGRESS` | JE-004, JE-005 | Responsive profile-aware Discover, Saved, and Applied workspace |

None of the `IN PROGRESS` rows may move to `DONE` until its own acceptance and
completion criteria pass.

## Current implementation order

1. Harden JE-005's existing search manager and Himalayas adapter against the
   stable JE-004 profile/snapshot boundary.
2. JE-006 may continue structural, accessibility, and mock-driven UI work while
   JE-005 finishes, then must update its API client and run full journeys
   against the final JE-004/005 contracts.
3. Batch 01 catalog runtime tests live under `tests/historical/` with explicit
   skip markers referencing ADR-001; JE-004 PostgreSQL tests cover the active
   Batch 02 profile/library contract.

When adding a pair, add its row in the same change as its Spec and Plan. A blocked
row must name its dependency or explain its external blocker directly below the
table.

## Deferred batches

- Scheduled ingestion and operational sync APIs
- Cross-provider duplicate detection and consolidation
- Additional live providers beyond Himalayas
- Distributed or multi-instance search-index coordination
- Authentication, sharing, and collaborative application tracking
- AI analysis, semantic search, resume matching, and application automation
