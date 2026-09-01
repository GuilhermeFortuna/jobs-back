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

**04 — Relevance ranking and wider coverage.** Profile skills as durable intent,
a deterministic skill- and query-aware relevance engine with index-side query and
location filtering, provider configuration separating credentialed from key-less
adapters, and three new providers: Adzuna, Remotive, and We Work Remotely.
Governed by
[ADR-002](decisions/ADR-002-skill-based-relevance-and-provider-credentials.md),
which extends ADR-001 rather than superseding it. Ranking ships before coverage
so added volume arrives into a working sort. Skills rank but never exclude.
Semantic search, AI ranking, authentication, and scheduling stay deferred.

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
| [JE-010](specs/JE-010-profile-skills.md) / [Plan](plans/JE-010-profile-skills.md) | 04 | `DONE` | JE-004 | Profile skills column, contract, shared normalizer, and search-cache invalidation |
| [JE-011](specs/JE-011-relevance-ranking-engine.md) / [Plan](plans/JE-011-relevance-ranking-engine.md) | 04 | `DONE` | JE-010 | Deterministic skill- and query-aware relevance scoring, match reporting, and location filter |
| [JE-012](specs/JE-012-provider-configuration-adzuna.md) / [Plan](plans/JE-012-provider-configuration-adzuna.md) | 04 | `READY` | JE-011 | Configured-versus-enabled provider resolution and the credentialed Adzuna adapter |
| [JE-013](specs/JE-013-remotive-weworkremotely-adapters.md) / [Plan](plans/JE-013-remotive-weworkremotely-adapters.md) | 04 | `BLOCKED` | JE-012 | Remotive JSON and We Work Remotely feed adapters behind the unchanged adapter contract |
| [JE-014](specs/JE-014-skills-and-ranking-workspace.md) / [Plan](plans/JE-014-skills-and-ranking-workspace.md) | 04 | `BLOCKED` | JE-011, JE-012 | Skills editor, ranking explainability, location filter, and provider availability in the UI |


None of the `IN PROGRESS` rows may move to `DONE` until its own acceptance and
completion criteria pass.

JE-009 is complete on branch `JE-009-multi-source-discovery-frontend`.

JE-010 is complete on branch `JE-010-profile-skills`.

JE-011 is complete on branch `JE-011-relevance-ranking-engine`.

JE-013 and JE-014 are `BLOCKED` only on the Batch 04
predecessors named in their `Depends on` column, not on any external condition.
Each becomes `READY` when its dependencies reach `DONE`.

## Current implementation order

1. Batches 01 through 03 are complete. Batch 01 catalog runtime tests live under
   `tests/historical/` with explicit skip markers referencing ADR-001; JE-004
   PostgreSQL tests cover the active profile/library contract.
2. Batch 04 runs strictly in order: JE-010 skills, then JE-011 relevance, then
   JE-012 provider configuration with Adzuna, then JE-013 Remotive and We Work
   Remotely. JE-010 through JE-013 are `jobs-back`; JE-014 is `jobs-front`.
3. JE-014 may proceed on structure once the JE-011 and JE-012 contracts are
   final, and must align with them before completion.
4. JE-010 and JE-011 share one normalization module. JE-010 lands it; JE-011
   extends it. A second normalizer is a defect in either task.

When adding a pair, add its row in the same change as its Spec and Plan. A blocked
row must name its dependency or explain its external blocker directly below the
table.

## Deferred batches

- Scheduled ingestion and operational sync APIs
- Skill suggestions, autocomplete, and inferred or resume-derived skills
- Distributed or multi-instance search-index coordination
- Authentication, sharing, and collaborative application tracking
- AI analysis, semantic search, resume matching, and application automation

