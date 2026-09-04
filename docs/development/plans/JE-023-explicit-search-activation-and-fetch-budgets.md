# JE-023 implementation plan: Explicit Search Activation and Fetch Budgets

**Status:** authoritative in [`../STATUS.md`](../STATUS.md)  
**Specification:** [`../specs/JE-023-explicit-search-activation-and-fetch-budgets.md`](../specs/JE-023-explicit-search-activation-and-fetch-budgets.md)  
**Depends on:** JE-022

## Current-system context

The frontend's `useJobScout.initializeFromApi` currently calls
`api.startSearch` when the URL contains filters and
`api.refreshDefaultSearch` otherwise. The latter reaches a forced backend
refresh even for the freshly created profile whose `SearchFilters` are all
empty. `retryConnection`, the profile-change effect, and `updateSkills` also
start searches without a Search or Refresh activation. `EMPTY_FILTERS`,
`hasUrlFilters`, the existing `idle` status kind, and the shared `EmptyState`
already provide the form comparison and presentation primitives this task
should extend rather than replace.

The backend accepts empty `SearchFilters`, interprets an empty provider list as
all live adapters, and starts `warm_defaults` during application lifespan.
`LiveSearchManager.start` already reuses an identical non-forced search for
twenty minutes, while default refresh deliberately uses `force=True` and keeps
stale results. Adzuna has an atomic per-search request budget, Jobicy and
Remotive have result caps, and We Work Remotely has a feed cap; Himalayas follows
every reported page and the manager has no per-search aggregate candidate cap.
JE-023 centralizes intent validation and applies the existing budget patterns to
every provider without changing the progressive-provider protocol.

## Provider-source baseline

Provider constraints were rechecked against primary sources on 2026-09-04.
Concrete defaults remain configuration, not assumptions about permanent
upstream policy.

| Provider | Primary source | Relevant constraint | Plan consequence |
| --- | --- | --- | --- |
| Himalayas | [Remote Jobs API reference](https://himalayas.app/docs/remote-jobs-api) | At most 20 jobs per browse request; rate limited; data cached for 24 hours | Ten-attempt and 200-item defaults; never queue every reported page |
| Remote OK | [Public API and terms](https://remoteok.com/api) | One board snapshot with attribution terms and no server-side count contract | One attempt; normalize at most 100 candidates and report partial output |
| Jobicy | [Jobs API documentation](https://jobicy.com/jobs-rss-feed) | `count` accepts 1–200; integrations should not poll more than hourly | Retain the conservative 50-item request and make the cap configurable |
| Adzuna | [Developer overview](https://developer.adzuna.com/overview) | Credentialed, country-scoped paginated search | Reduce the per-search attempt default from 50 to 10 and add a 200-item cap |
| Remotive | [Official public API repository](https://github.com/remotive-io/remote-jobs-api) | Advises at most four fetches per day and blocks more than two per minute | One attempt and 50 items; no implicit lifecycle request |
| We Work Remotely | [Official RSS endpoint](https://weworkremotely.com/remote-jobs.rss) | Single public feed rather than query pagination | One attempt; reduce normalized feed cap from 500 to 100 |

## Interfaces produced

```ts
// jobs-front/src/lib/search-params.ts
export function hasSearchCriteria(filters: SearchFilters): boolean;
```

```python
# jobs-back/src/jobs_back/schemas/discovery.py
class SearchFilters(BaseModel):
    def has_search_criteria(self) -> bool: ...

# jobs-back/src/jobs_back/config.py
class Settings(BaseSettings):
    search_max_candidates_per_search: int

# jobs-back/src/jobs_back/api/searches.py
def require_search_criteria(filters: SearchFilters) -> SearchFilters: ...

# Representative adapter signatures; each existing adapter receives the
# applicable subset without changing ProgressiveProvider.pages.
class HimalayasProvider:
    def __init__(
        self,
        *,
        request_budget: int = 10,
        result_cap: int = 200,
        concurrency: int = 12,
        timeout: float = 20,
        max_retries: int = 3,
    ) -> None: ...

class AdzunaProvider:
    def __init__(
        self,
        *,
        request_budget: int = 10,
        result_cap: int = 200,
        **existing: object,
    ) -> None: ...
```

## Implementation decisions

- Search authorization is defined as an explicit UI activation, not inferred
  from populated defaults or a URL, because restoring state must not silently
  authorize external requests.
- The frontend and backend use equivalent substantive-criteria predicates,
  with the same criteria table asserted in both test suites, because a UI-only
  check is bypassable while divergent definitions would reject requests the
  interface permits.
- Provider selection, sort, and skills do not count as substantive criteria,
  because none guarantees that an upstream adapter can avoid a board-wide
  response. Skills remain ranking-only under JE-010 and JE-011.
- `initializeFromApi` becomes metadata-and-form initialization only. It leaves
  `statusKind` as `idle`, because overloading `empty` would falsely claim a
  completed search found no matches.
- The primary Search control is disabled with persistent `aria-describedby`
  help when the current filters are non-actionable, and Refresh Default is
  disabled with equivalent help when saved defaults are non-actionable, because
  prevention must remain understandable to keyboard and screen-reader users.
- URL parameters continue to win over saved defaults but only prefill the form,
  because deep-link convenience does not outweigh the explicit-activation
  boundary.
- Backend startup removes default warming rather than teaching the warmer to
  skip only empty profiles, because even a meaningful saved default is not user
  authorization at process-start time.
- Ordinary Search continues through the non-forced start path and therefore
  keeps the existing twenty-minute canonical-filter reuse. Refresh Default is
  the sole force path, because its label communicates that new provider work is
  requested.
- Connection retry, profile switching, and skill updates stop polling and
  restore local state without starting provider work, because recovery and
  editing actions are not search actions. Skill updates retain visible results
  but announce that Search must be run again to apply the new ranking.
- Criteria validation happens before `LiveSearchManager.start` allocates a
  state, because a rejected request must consume neither memory nor provider
  budget. Both search endpoints map the same domain error to the existing 422
  validation response.
- Attempt budgets live inside paginated adapters and reserve atomically before
  every transport attempt, following Adzuna's `_RequestBudget`, because a
  manager-side item cap cannot prevent Himalayas workers from already issuing
  every queued page.
- Candidate caps are enforced by adapters before yielding and again by the
  manager at the 1,000-item aggregate boundary, because adapter defects or
  deployment overrides must not remove the system-wide fail-safe.
- A batch with both usable items and a truncation warning sets `had_success` and
  `incomplete`, because treating warning-bearing data as a provider failure
  would discard the distinction between bounded partial success and no result.
- The manager cancels remaining provider consumers when the aggregate ceiling
  is reached and marks those trackers incomplete, because continuing upstream
  work after no more candidates can be accepted only spends quota.
- Truncation is represented through the existing warnings and `is_partial`
  fields, because callers must be able to distinguish a complete bounded result
  set from the full upstream universe without a new response shape.
- Snapshot providers retain one transport request and stop normalization at
  their item cap, because their public endpoints offer no reliable response-byte
  pagination. Documentation and tests state this limitation rather than
  claiming an item cap saves download bandwidth.
- Budget defaults flow through existing provider `options` and validated search
  settings, because operators need lower ceilings without a code change and
  secrets must remain separate from budget configuration.
- Provider attempt options accept 1–50, provider candidate options accept
  1–1,000, and `SEARCH_MAX_CANDIDATES_PER_SEARCH` accepts 1–10,000, because a
  configuration escape hatch must not turn malformed or extreme values back
  into an unbounded crawl.
- Persistent daily quota accounting is not added here, because JE-012 explicitly
  excluded it and it requires a transactional quota model of its own. JE-023
  still eliminates all implicit quota use and bounds every explicit search.

## Ordered implementation

1. Use `JE-023-explicit-search-activation-and-fetch-budgets` from `development`
   in both repositories, creating the matching branch where it is missing,
   preserving any pre-existing uncommitted work, and committing only JE-023
   changes.
2. Add shared frontend fixture cases for substantive criteria: empty, provider
   only, sort only, and skills-adjacent state are false; keyword, location,
   country, explicit worldwide, seniority, employment type, salary, and posting
   age are true. Confirm the tests fail, implement `hasSearchCriteria`, confirm
   they pass, and commit.
3. Add hook tests asserting initial mount with empty defaults, meaningful
   defaults, and URL filters makes zero `/searches` and zero
   `/default-search/refresh` calls while restoring the expected form and idle
   state. Confirm they fail, remove mount-time execution, add the distinct idle
   empty-state copy, confirm they pass, and commit.
4. Add hook tests asserting retry, profile creation/switch, default saving, and
   skill updates make zero search-creation calls; assert skill updates retain
   current results and announce that an explicit rerun is required. Confirm they
   fail, remove those implicit triggers, confirm they pass, and commit.
5. Add frontend validation tests asserting Search and Refresh are disabled for
   empty, provider-only, and sort-only state, reference persistent accessible
   missing-criterion help, and do not clear the form. Confirm they fail, wire
   the predicate into both explicit actions and controls, confirm they pass, and
   commit.
6. Add backend predicate and API tests with the same criteria matrix. Assert an
   invalid create or refresh returns 422, creates no manager state, and calls no
   fake provider. Confirm they fail, implement domain validation before manager
   start, confirm they pass, and commit.
7. Replace the startup-warming lifecycle test with one asserting that profiles
   with empty and meaningful defaults both produce zero provider calls and zero
   search states on startup. Confirm it fails, remove warming while retaining
   eviction startup and shutdown cancellation, confirm it passes, and commit.
8. Add failing Himalayas tests proving an upstream total of 10,000 schedules no
   more than 10 transport attempts and yields no more than 200 normalized
   candidates, including retries and concurrent workers. Generalize Adzuna's
   atomic budget helper for reuse or mirror its tested semantics, implement both
   caps, confirm the tests pass, and commit.
9. Add failing Remote OK, Jobicy, Remotive, and We Work Remotely contract tests
   for one attempt and candidate totals of 100, 50, 50, and 100 respectively.
   Implement configurable caps and sanitized truncation warnings, confirm all
   tests pass, and commit.
10. Add registry/configuration tests proving every new option accepts a positive
    bounded integer, rejects or safely defaults malformed values, and uses the
    exact table defaults. Confirm they fail, pass options through the existing
    registry factory, confirm they pass, and commit.
11. Add multi-provider tests with raised adapter limits that emit more than
    1,000 candidates. Confirm they fail, enforce the aggregate cap, cancel
    remaining consumers, mark affected trackers incomplete, and assert a partial
    result with no more than 1,000 accepted candidates. Assert a warning-bearing
    batch with usable items counts as successful and incomplete rather than
    failed; confirm they pass and commit.
12. Add integration regressions proving one explicit actionable Search creates
    one fan-out, polling and pagination create none, the same ordinary search
    reuses its state within twenty minutes, and explicit Refresh creates exactly
    one replacement while serving stale results. Confirm failures before any
    adjustment, preserve the JE-005 through JE-014 contracts, confirm green, and
    commit.
13. Run the human network check from the specification: start the full stack,
    clear the network log, and record request counts for load, reload, profile
    switch, skill update, retry, Search, and Refresh. Commit only documentation
    corrections arising from the check.
14. Run both full CI suites, `git diff --check`, and the focused live-stack
    browser journey. Update the JE-023 row to `DONE` only when every acceptance
    criterion passes, then commit the status update separately.

## Validation

- **Unit:** Frontend and backend criteria matrices; hook activation boundaries;
  adapter attempt, retry, concurrency, and candidate caps.
- **Integration:** API rejection before state creation; one explicit fan-out;
  twenty-minute reuse; explicit forced refresh with stale results; aggregate
  cancellation and partial status.
- **Regression:** Profile isolation, progressive status, provider attribution,
  deterministic relevance, consolidation, pagination, and saved/applied library
  suites remain unchanged.
- **Manual:** Browser network log proves lifecycle events issue zero search
  requests and each explicit activation issues exactly one.
- **Measurement:** Record upstream attempts and checked candidates for every
  provider under an intentionally high-total fixture and compare them with the
  limits table; every value must be at or below its ceiling.

```bash
cd /home/gui/projects/jobs/jobs-back
./ci.sh
git diff --check

cd /home/gui/projects/jobs/jobs-front
./ci.sh all
git diff --check

cd /home/gui/projects/jobs
./dev.sh
```

## Handoff

Report the request count observed for every non-search lifecycle action, the
ordinary Search and forced Refresh counts, each provider's measured transport
attempt and normalized-candidate maximum, the aggregate accepted-candidate
maximum, the exact warning and partial-state behavior at every ceiling, the
twenty-minute reuse regression result, both CI summaries including skipped-test
counts, and the human network-check result. Call out that single-response feed
caps bound processing and retention rather than response bytes, and list any
provider whose current official policy changed from the source baseline above.
