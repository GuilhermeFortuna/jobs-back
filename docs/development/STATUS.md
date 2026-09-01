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

**Batch 01 — Backend foundation.** Establishes the normalized PostgreSQL model,
provider-neutral ingestion path, and searchable read API. It deliberately defers
concrete providers, scheduling, frontend discovery, and cross-provider
deduplication.

| ID | Batch | Status | Depends on | Deliverable |
| --- | --- | --- | --- | --- |
| [001](specs/001-normalized-job-model.md) / [Plan](plans/001-normalized-job-model.md) | 01 | `READY` | None | Normalized PostgreSQL job model, validation, migration, and lifecycle fields |
| [002](specs/002-provider-ingestion.md) / [Plan](plans/002-provider-ingestion.md) | 01 | `BLOCKED` | 001 | Provider adapter contract, atomic ingestion service, sync-run tracking, and manual runner |
| [003](specs/003-job-search-api.md) / [Plan](plans/003-job-search-api.md) | 01 | `BLOCKED` | 001 | Filtered and deterministically sorted job list and detail API |

## Current implementation order

1. Implement 001 and mark it `DONE` only after its migration, PostgreSQL tests,
   and completion criteria pass.
2. Once 001 is done, 002 and 003 become `READY`. They may be implemented in
   parallel because the search read path does not depend on ingestion code.
3. Mark each pair `IN PROGRESS` when implementation begins and `DONE` only after
   all completion criteria in its Plan pass.

When adding a pair, add its row in the same change as its Spec and Plan. A blocked
row must name its dependency or explain its external blocker directly below the
table.

## Deferred batches

- Concrete provider selection and adapters, including current API and terms
  verification
- Scheduled ingestion and operational sync APIs
- Cross-provider duplicate detection and consolidation
- Frontend job discovery, filtering, results, and detail views
- AI analysis, semantic search, resume matching, and application automation

