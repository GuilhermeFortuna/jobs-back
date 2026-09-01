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
and durable saved/applied snapshots only. JE-005 and JE-006 are complete against
the final JE-004/005 API contracts.

**03 — Multi-provider coverage and consolidation.** Provider registry and
concurrent fan-in across Himalayas, RemoteOK, and Jobicy behind the existing
adapter contract, deterministic duplicate consolidation in the in-memory index
and in the personal library, and multi-source attribution in the workspace.
Consolidation adds fields to saved snapshots only; provider catalogs, search
indexes, and result pages remain unpersisted under ADR-001. Scheduling,
authentication, and AI features stay deferred.

## Tasks


| ID                                                                                                                                | Batch | Status | Depends on     | Deliverable                                                                                |
| --------------------------------------------------------------------------------------------------------------------------------- | ----- | ------ | -------------- | ------------------------------------------------------------------------------------------ |
| [JE-001](specs/JE-001-normalized-job-model.md) / [Plan](plans/JE-001-normalized-job-model.md)                                     | 01    | `DONE` | None           | Normalized PostgreSQL job model, validation, migration, and lifecycle fields               |
| [JE-002](specs/JE-002-provider-ingestion.md) / [Plan](plans/JE-002-provider-ingestion.md)                                         | 01    | `DONE` | JE-001         | Provider adapter contract, atomic ingestion service, sync-run tracking, and manual runner  |
| [JE-003](specs/JE-003-job-search-api.md) / [Plan](plans/JE-003-job-search-api.md)                                                 | 01    | `DONE` | JE-001         | Filtered and deterministically sorted job list and detail API                              |
| [JE-004](specs/JE-004-trusted-profiles-personal-library.md) / [Plan](plans/JE-004-trusted-profiles-personal-library.md)           | 02    | `DONE` | None           | Trusted profiles, default preferences, and isolated saved/applied snapshots                |
| [JE-005](specs/JE-005-live-provider-search-himalayas.md) / [Plan](plans/JE-005-live-provider-search-himalayas.md)                 | 02    | `DONE` | JE-004         | Per-profile progressive in-memory search and hardened Himalayas adapter                    |
| [JE-006](specs/JE-006-personal-job-discovery-frontend.md) / [Plan](plans/JE-006-personal-job-discovery-frontend.md)               | 02    | `DONE` | JE-004, JE-005 | Responsive profile-aware Discover, Saved, and Applied workspace                            |
| [JE-007](specs/JE-007-multi-provider-search-fan-in.md) / [Plan](plans/JE-007-multi-provider-search-fan-in.md)                     | 03    | `DONE` | JE-005         | Provider registry and concurrent multi-provider fan-in with RemoteOK and Jobicy adapters   |
| [JE-008](specs/JE-008-cross-provider-duplicate-consolidation.md) / [Plan](plans/JE-008-cross-provider-duplicate-consolidation.md) | 03    | `DONE` | JE-007         | Deterministic cross-provider duplicate consolidation in memory and in the personal library |
| [JE-009](specs/JE-009-multi-source-discovery-frontend.md) / [Plan](plans/JE-009-multi-source-discovery-frontend.md)               | 03    | `DONE` | JE-007, JE-008 | Multi-source attribution, per-provider status, and provider filtering in the workspace     |


None of the `IN PROGRESS` rows may move to `DONE` until its own acceptance and
completion criteria pass.

JE-009 is complete on branch `JE-009-multi-source-discovery-frontend`.

## Current implementation order

1. Batch 02 frontend (JE-006) is complete against the final JE-004/005 contracts.
2. Batch 01 catalog runtime tests live under `tests/historical/` with explicit
  skip markers referencing ADR-001; JE-004 PostgreSQL tests cover the active
   Batch 02 profile/library contract.
3. Batch 03 runs strictly in order: JE-007 fan-in, then JE-008 consolidation,
  then JE-009 frontend. JE-007 and JE-008 are `jobs-back`; JE-009 is
   `jobs-front`.

When adding a pair, add its row in the same change as its Spec and Plan. A blocked
row must name its dependency or explain its external blocker directly below the
table.

## Deferred batches

- Scheduled ingestion and operational sync APIs
- Distributed or multi-instance search-index coordination
- Authentication, sharing, and collaborative application tracking
- AI analysis, semantic search, resume matching, and application automation

