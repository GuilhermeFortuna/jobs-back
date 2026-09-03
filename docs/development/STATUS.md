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

**05 — Frontend redesign and component sourcing.** A full visual redesign of the
workspace, sourced from configured premium component registries rather than
hand-rolled markup. Batches 02 and 03 instructed agents to source from React
Bits, Magic UI, 21st.dev and Aceternity/Cult UI, but `components.json` configured
no registry and the installed shadcn skill forbids guessing one, so the
instruction was unexecutable. JE-015 fixes that tooling before any pixel changes.
The information architecture is fixed: three panes on desktop, three views,
profile picker in the header, sheet-versus-pane detail across one breakpoint.
Light, dark and system themes ship with an explicit toggle. Working surfaces stay
dense and calm; animated components are placed at pass-through moments — the
header band, empty states, search-in-progress, and the profile surface — each
with a reduced-motion and mobile fallback. No backend contract changes. Semantic
search, AI ranking, authentication and scheduling stay deferred.

## Tasks


| ID                                                                                                                                | Batch | Status    | Depends on     | Deliverable                                                                                     |
| --------------------------------------------------------------------------------------------------------------------------------- | ----- | --------- | -------------- | ----------------------------------------------------------------------------------------------- |
| [JE-001](specs/JE-001-normalized-job-model.md) / [Plan](plans/JE-001-normalized-job-model.md)                                     | 01    | `DONE`    | None           | Normalized PostgreSQL job model, validation, migration, and lifecycle fields                    |
| [JE-002](specs/JE-002-provider-ingestion.md) / [Plan](plans/JE-002-provider-ingestion.md)                                         | 01    | `DONE`    | JE-001         | Provider adapter contract, atomic ingestion service, sync-run tracking, and manual runner       |
| [JE-003](specs/JE-003-job-search-api.md) / [Plan](plans/JE-003-job-search-api.md)                                                 | 01    | `DONE`    | JE-001         | Filtered and deterministically sorted job list and detail API                                   |
| [JE-004](specs/JE-004-trusted-profiles-personal-library.md) / [Plan](plans/JE-004-trusted-profiles-personal-library.md)           | 02    | `DONE`    | None           | Trusted profiles, default preferences, and isolated saved/applied snapshots                     |
| [JE-005](specs/JE-005-live-provider-search-himalayas.md) / [Plan](plans/JE-005-live-provider-search-himalayas.md)                 | 02    | `DONE`    | JE-004         | Per-profile progressive in-memory search and hardened Himalayas adapter                         |
| [JE-006](specs/JE-006-personal-job-discovery-frontend.md) / [Plan](plans/JE-006-personal-job-discovery-frontend.md)               | 02    | `DONE`    | JE-004, JE-005 | Responsive profile-aware Discover, Saved, and Applied workspace                                 |
| [JE-007](specs/JE-007-multi-provider-search-fan-in.md) / [Plan](plans/JE-007-multi-provider-search-fan-in.md)                     | 03    | `DONE`    | JE-005         | Provider registry and concurrent multi-provider fan-in with RemoteOK and Jobicy adapters        |
| [JE-008](specs/JE-008-cross-provider-duplicate-consolidation.md) / [Plan](plans/JE-008-cross-provider-duplicate-consolidation.md) | 03    | `DONE`    | JE-007         | Deterministic cross-provider duplicate consolidation in memory and in the personal library      |
| [JE-009](specs/JE-009-multi-source-discovery-frontend.md) / [Plan](plans/JE-009-multi-source-discovery-frontend.md)               | 03    | `DONE`    | JE-007, JE-008 | Multi-source attribution, per-provider status, and provider filtering in the workspace          |
| [JE-010](specs/JE-010-profile-skills.md) / [Plan](plans/JE-010-profile-skills.md)                                                 | 04    | `DONE`    | JE-004         | Profile skills column, contract, shared normalizer, and search-cache invalidation               |
| [JE-011](specs/JE-011-relevance-ranking-engine.md) / [Plan](plans/JE-011-relevance-ranking-engine.md)                             | 04    | `DONE`    | JE-010         | Deterministic skill- and query-aware relevance scoring, match reporting, and location filter    |
| [JE-012](specs/JE-012-provider-configuration-adzuna.md) / [Plan](plans/JE-012-provider-configuration-adzuna.md)                   | 04    | `DONE`    | JE-011         | Configured-versus-enabled provider resolution and the credentialed Adzuna adapter               |
| [JE-013](specs/JE-013-remotive-weworkremotely-adapters.md) / [Plan](plans/JE-013-remotive-weworkremotely-adapters.md)             | 04    | `DONE`    | JE-012         | Remotive JSON and We Work Remotely feed adapters behind the unchanged adapter contract          |
| [JE-014](specs/JE-014-skills-and-ranking-workspace.md) / [Plan](plans/JE-014-skills-and-ranking-workspace.md)                     | 04    | `DONE`    | JE-011, JE-012 | Skills editor, ranking explainability, location filter, and provider availability in the UI     |
| [JE-015](specs/JE-015-component-sourcing-infrastructure.md) / [Plan](plans/JE-015-component-sourcing-infrastructure.md)           | 05    | `DONE`    | None           | Configured component registries, Claude Code MCP access, and a verified component source ledger |
| [JE-016](specs/JE-016-design-system-foundation.md) / [Plan](plans/JE-016-design-system-foundation.md)                             | 05    | `DONE`    | JE-015         | Color, elevation, type and motion tokens, light/dark/system theming, and new design references  |
| [JE-017](specs/JE-017-redesign-resilient-test-contracts.md) / [Plan](plans/JE-017-redesign-resilient-test-contracts.md)           | 05    | `DONE`    | JE-015         | Structure-coupled assertions converted to behavioral contracts before any restyle               |
| [JE-018](specs/JE-018-primitive-layer-completion.md) / [Plan](plans/JE-018-primitive-layer-completion.md)                         | 05    | `DONE`    | JE-016, JE-017 | Missing primitives installed from the ledger and hand-rolled duplicates removed                 |
| [JE-019](specs/JE-019-application-shell-and-theme-surface.md) / [Plan](plans/JE-019-application-shell-and-theme-surface.md)       | 05    | `DONE`    | JE-018         | Header, navigation, pane chrome, theme control, and the header-band ambient treatment           |
| [JE-020](specs/JE-020-discovery-surfaces-redesign.md) / [Plan](plans/JE-020-discovery-surfaces-redesign.md)                       | 05    | `READY`   | JE-019         | Filters panel, job card with company logos, skeletons, pagination, and empty states             |
| [JE-021](specs/JE-021-detail-library-and-status-surfaces.md) / [Plan](plans/JE-021-detail-library-and-status-surfaces.md)         | 05    | `READY`   | JE-019         | Job detail tabs, unified status alerts, search-in-progress treatment, and the skills surface    |


None of the `IN PROGRESS` rows may move to `DONE` until its own acceptance and
completion criteria pass.

JE-009 is complete on branch `JE-009-multi-source-discovery-frontend`.

JE-010 is complete on branch `JE-010-profile-skills`.

JE-011 is complete on branch `JE-011-relevance-ranking-engine`.

JE-012 is complete on branch `JE-012-provider-configuration-adzuna`.

JE-013 is complete on branch `JE-013-remotive-weworkremotely-adapters`.

JE-014 is complete on branch `JE-014-skills-and-ranking-workspace`.

JE-015 is complete on branch `JE-015-component-sourcing-infrastructure`.

JE-016 is complete on branch `JE-016-design-system-foundation`.

JE-017 is complete on branch `JE-017-redesign-resilient-test-contracts`
(`jobs-front`).

JE-016 and JE-017 became `READY` together once JE-015 was `DONE`, and ran in
parallel — JE-016 substitutes tokens without restructuring markup, so it did
not depend on JE-017. Both are now `DONE`, so JE-018 is `READY`.

JE-018 is complete on branch `JE-018-primitive-layer-completion`.

JE-019 is complete on branch `JE-019-application-shell-and-theme-surface`
(`jobs-front`). Shell chrome uses ledger Tabs navigation, a single profile
picker mount, one theme control, Card pane elevation tokens, and
`@magicui/flickering-grid` confined to the header band. Ambient ships animated
on `sm+` when motion is allowed; mobile (`max-width: 639px`) and
`prefers-reduced-motion` use a static radial-grid fallback. Desktop FCP with
ambient mounted measured 112ms (paint timing); no static desktop fallback
required. The mobile tab bar is a viewport-fixed sibling of the header (not
nested under `backdrop-blur`) so `position: fixed` is not trapped by the header
containing block.

JE-020 and JE-021 are `READY` after JE-019. They own disjoint files, so they may
run in parallel. JE-020 is authoritative for the shared company-logo component
and the empty-state treatment; JE-021 consumes both rather than writing its own.

External blocker on Batch 05, affecting JE-015 only: `TWENTY_FIRST_API_KEY` is
not set in the environment, so the configured 21st.dev MCP server cannot
authenticate. JE-015 treats that registry as optional and degrades to the
remaining registries, so this does not block the batch — but 21st.dev components
are unavailable until the key is supplied, which is a user action.

## Current implementation order

1. Batches 01 through 03 are complete. Batch 01 catalog runtime tests live under
  `tests/historical/` with explicit skip markers referencing ADR-001; JE-004
   PostgreSQL tests cover the active profile/library contract.
2. Batch 04 is complete: JE-010 through JE-014.
3. JE-010 and JE-011 share one normalization module. JE-010 lands it; JE-011
  extends it. A second normalizer is a defect in either task.
4. Batch 05 is entirely `jobs-front`. It runs JE-015 first, then JE-016 and
  JE-017 in parallel, then JE-018, then JE-019, then JE-020 and JE-021 in
   parallel.
5. No Batch 05 task may install a component the JE-015 ledger does not list. A
  component sourced outside the ledger is a defect in the task that added it —
   this is the rule whose absence caused the original sourcing failure.
6. No Batch 05 task changes `src/hooks/use-job-scout.ts` or any module under
  `src/lib/`. The redesign is composition and tokens; the state layer and the
   pure logic are consumed as they are. A diff in either is a defect.
7. No Batch 05 task changes a backend contract. A redesign requirement that
  appears to need one — pagination and company logos are the candidates — is
   reported as a finding rather than worked around client side.

When adding a pair, add its row in the same change as its Spec and Plan. A blocked
row must name its dependency or explain its external blocker directly below the
table.

## Deferred batches

- Scheduled ingestion and operational sync APIs
- Skill suggestions, autocomplete, and inferred or resume-derived skills
- Distributed or multi-instance search-index coordination
- Authentication, sharing, and collaborative application tracking
- AI analysis, semantic search, resume matching, and application automation

