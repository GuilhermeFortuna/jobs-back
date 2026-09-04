# JE-023 — Explicit Search Activation and Fetch Budgets Specification

**Status:** authoritative in [`../STATUS.md`](../STATUS.md)  
**Project direction:** [`../../job-engine-v1-goal.md`](../../job-engine-v1-goal.md)  
**Depends on:** JE-022  
**Implementation plan:** [`../plans/JE-023-explicit-search-activation-and-fetch-budgets.md`](../plans/JE-023-explicit-search-activation-and-fetch-budgets.md)

## Purpose

Job Scout currently starts live provider work during backend startup and during
ordinary frontend lifecycle events, including the first visit by a profile whose
preferences are completely empty. An empty provider selection means every
enabled provider, so merely opening the application can inspect thousands of
unrelated positions, consume credentialed-provider quota, and repeat the work on
reload. This task makes provider traffic an explicit user decision and adds
defence-in-depth budgets so one authorized search cannot expand into an
unbounded provider crawl.

## Requirements

### Explicit activation boundary

- A provider search begins only after the user explicitly activates the primary
  search action or the default-search refresh action.
- Backend process startup, frontend mount or reload, URL restoration, connection
  retry, profile creation or selection, saving defaults, and editing skills must
  perform zero provider requests.
- Polling and pagination may continue a search that the user explicitly started;
  they must not create a second provider search.
- A profile's saved defaults and URL parameters prefill the search form but do
  not execute it. This makes visible form state an input proposal rather than
  silent authorization to spend provider capacity.
- Updating skills may mark visible results as needing a rerun, but must not
  rerank by launching provider work automatically.

### Meaningful search criteria

- A search is actionable only when it contains at least one substantive job
  criterion: a non-blank keyword or role location, an eligibility country, an
  explicit worldwide choice, at least one seniority or employment type, a
  salary floor, or a posting-age limit.
- Sort order, provider selection, and profile skills do not qualify on their
  own. They change ordering, source scope, or local ranking without necessarily
  narrowing what an upstream provider must return.
- The interface prevents an empty or non-substantive search and explains which
  criterion is required without clearing the user's form. The primary Search
  control is disabled while criteria are non-actionable and is paired with
  persistent accessible help; the default-refresh control is likewise disabled
  when the saved defaults are non-actionable.
- Both search creation and default-search refresh reject non-actionable filters
  at the API boundary before a search state, task, quota counter, or provider
  request is created. A direct client therefore cannot bypass the interface
  guard.
- Rejection uses the existing validation-error presentation path and identifies
  the missing search criterion without exposing provider configuration.

### Startup and lifecycle behavior

- Backend startup performs maintenance and eviction setup only; it does not warm
  profile defaults through provider calls.
- A successful frontend initialization ends in an idle, ready-to-search state
  with the selected profile and resolved filters visible.
- The idle Discover surface clearly states that no search has run and presents
  the primary search action. It must not describe the state as “no matching
  roles,” because no comparison has occurred.
- Retrying a recovered backend reloads local profile and provider metadata only.
  The user must activate Search or Refresh before live provider work resumes.
- Switching profiles cancels any client polling for the previous profile,
  restores the next profile's form, and remains idle.
- An ordinary repeated search with the same profile and canonical filters keeps
  the existing twenty-minute in-memory reuse behavior. Only the explicitly
  labelled refresh action may force a new provider run.

### Provider fetch budgets

- Every provider has a finite default attempt budget and candidate-item budget
  for one search. No upstream-reported total may schedule work beyond those
  budgets.
- The safe defaults are:

  | Provider | Maximum upstream attempts | Maximum normalized candidates |
  | --- | ---: | ---: |
  | Himalayas | 10 | 200 |
  | Remote OK | 1 | 100 |
  | Jobicy | 1 | 50 |
  | Adzuna | 10 | 200 |
  | Remotive | 1 | 50 |
  | We Work Remotely | 1 | 100 |

- A search also has an aggregate ceiling of 1,000 normalized candidates across
  providers. The aggregate ceiling remains effective if deployment
  configuration raises individual provider budgets.
- Initial requests, page requests, and transport-started retries all consume the
  attempt budget. A locally rejected search consumes nothing.
- Concurrent page workers reserve budget atomically before transport begins, so
  concurrency cannot overshoot a ceiling.
- Reaching an attempt, item, or aggregate ceiling stops additional work,
  preserves already accepted results, marks the affected search partial, and
  reports a sanitized provider-specific truncation warning.
- Budget values are deployment-configurable through the existing provider and
  search configuration mechanisms, validated as positive bounded integers, and
  never inferred from an upstream result count. Per-provider attempts are
  bounded to 1–50, per-provider candidates to 1–1,000, and the aggregate
  candidate ceiling to 1–10,000.
- Single-response feeds may transfer a payload larger than their normalized
  candidate cap; their adapters must stop normalization and retention at the
  cap and report that the result set is partial. The application must not claim
  that an item cap also caps response bytes.

### Provider and product guarantees retained

- Results remain live and process-local; ordinary search results are not added
  to PostgreSQL.
- Multi-provider fan-in, deterministic relevance ranking, duplicate
  consolidation, progressive status, stale-result preservation during an
  explicit refresh, pagination, provider attribution, and profile isolation
  remain intact.
- Missing credentials continue to make a provider unconfigured rather than
  failing application startup.
- Provider failures and budget exhaustion remain isolated: healthy providers'
  results survive and the overall search is partial rather than failed when at
  least one provider succeeds.
- Saved and applied library behavior is unchanged.

## Constraints and non-goals

- No scheduled ingestion, persistent provider catalogue, or database storage of
  ordinary search results.
- No background recommendations. Profile skills continue to rank an explicitly
  requested result set; they do not authorize a broad fetch.
- No automatic search merely because a URL contains filters. URLs restore form
  intent only.
- No promise of account-wide or cross-process daily quota enforcement. This task
  prevents implicit consumption and bounds each search; a persistent quota
  ledger remains separate operational work.
- No provider-response cache shared across distinct filters or profiles.
- No change to provider credential names, attribution requirements, or external
  terms of use.
- No redesign beyond the idle and validation messages needed to make activation
  state unambiguous.

## Acceptance criteria

### Agent-verifiable

1. Starting the backend with profiles present creates no search state and makes
   zero calls to every provider adapter.
2. Opening or reloading the frontend with empty defaults, meaningful saved
   defaults, or filter-bearing URL parameters makes no search or refresh request
   and displays the restored form in the idle state.
3. Connection retry, profile creation or switching, default saving, and skill
   updates make no search or refresh request.
4. Submitting an actionable search starts exactly one provider fan-out; polling
   and pagination read that search without starting another.
5. Empty filters, provider-only filters, sort-only changes, and skills-only
   profiles are rejected before search state creation with zero provider calls.
6. The explicit default-refresh action rejects empty defaults and forces one new
   run for actionable defaults while preserving stale results until replacement.
7. Repeating an ordinary actionable search with identical canonical filters
   within twenty minutes reuses the existing search state.
8. Contract tests prove each provider's default attempt and candidate ceilings,
   prove retries consume attempts, and prove concurrent pagination cannot
   overshoot.
9. Aggregate-cap tests prove no search accepts more than 1,000 normalized
   candidates even when individual budgets are configured higher.
10. Every budget-exhaustion path retains accepted results, reports a sanitized
    warning, and produces a partial completed search when another provider
    succeeds.
11. A provider batch containing usable items and a truncation warning counts as
    a successful but incomplete provider result, never as a failed provider.
12. The idle Discover state says no search has run, while a completed zero-result
    search continues to say no roles matched; the two states have distinct
    accessible text.
13. Frontend and backend full CI suites pass, including production build and
    browser journeys, with PostgreSQL tests running only against the isolated
    test database.

### Human-verifiable

1. With browser network tools open, loading the application, switching profiles,
   editing skills, and retrying a healthy backend show no search-creation or
   default-refresh request until Search or Refresh is clicked.  
   Command: `cd /home/gui/projects/jobs && ./dev.sh`
