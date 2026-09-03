# JE-005 — Live Provider Search and Himalayas Implementation Plan

Implements
[`JE-005-live-provider-search-himalayas.md`](../specs/JE-005-live-provider-search-himalayas.md)
after the JE-004 profile contract is stable.

## Implementation baseline — reuse, do not rebuild

| Existing work | Current evidence | Disposition |
| --- | --- | --- |
| `providers/himalayas.py` | Async client, upstream filters, bounded page workers, live normalization | Retain and harden; a live query completed with 17 normalized results |
| `search/live.py` | Process-local states, background population, partial paging, local salary/date filters and final sorts | Retain; add lifecycle, stale refresh, failure retention, and concurrency safety |
| `api/searches.py` | Create/get/default-refresh endpoints | Retain; correct async/service boundaries and stale-refresh response contract |
| `schemas/discovery.py` | Search filters/result/progressive page schemas | Retain; strengthen validation and provider-neutral naming |
| `main.py` lifespan | Creates and closes one search manager | Retain; add default warming and deployment constraint documentation |

Verified live-contract corrections already incorporated and not to be rediscovered
as new work: upstream `sort=relevant`, `guid` identity, list-valued seniority,
empty logo URLs, and Unix-second timestamps. Ruff passes. No JE-005 automated
test suite exists yet.

## Remaining implementation

### Adapter hardening

1. Introduce a provider protocol so the manager is testable with fake progressive
   providers and future adapters do not couple to Himalayas.
2. Normalize every documented/live compensation period and employment value;
   contract-test country-name strings and documented country objects, seconds,
   milliseconds, RFC timestamps, empty/null URLs, and malformed required rows.
3. Add bounded retry/backoff for 429, timeouts, and transient 5xx responses.
   Honor `Retry-After`, cap attempts, and expose sanitized warnings.
4. Replace eager creation of one task per upstream page with a fixed worker queue
   that remains bounded even for a very broad search.
5. Preserve accepted raw objects internally for JE-004 without returning them in
   search JSON. Sanitize or text-render descriptions.

### Search manager lifecycle

1. Protect shared state with explicit event-loop-safe synchronization and define
   how clients observe pages while workers append results.
2. Make progress monotonic independent of page completion order. Track expected
   and completed pages separately rather than assigning progress from whichever
   page finishes last.
3. Retain collected items on later-page failure and distinguish partial failure
   from complete failure.
4. Implement stale-while-refresh: keep the previous compatible completed index,
   expose the replacement search ID, then atomically promote it when useful.
5. Warm every profile's default search asynchronously on startup without
   delaying `/health` or application readiness.
6. Add TTL and memory-bound eviction, explicit `410` behavior, cancellation, and
   cleanup. Prevent abandoned states/tasks from growing without bound.
7. Keep V1 single-process. Document that multiple Uvicorn workers/replicas would
   not share search IDs.

### Filtering, sorting, and API

1. Canonicalize filter keys so equivalent requests reuse a warm index.
2. Confirm which filters Himalayas supports upstream, translate provider-neutral
   enums explicitly, and apply unsupported semantics locally.
3. Guarantee nullable totals while loading and exact totals/final deterministic
   sort only after completion. Define behavior for a requested page not yet
   populated.
4. Expose a manager lookup used by JE-004 to resolve a search result
   authoritatively by search/provider identity.
5. Bound expensive unconstrained searches operationally without changing the
   user's requested matching set silently.

## Test plan

- Fake-provider tests for partial pages, out-of-order completion, monotonic
  progress, final totals/sort, reuse, refresh, eviction, cancellation, and
  partial-page failure.
- HTTP-mocked Himalayas tests for query parameters, fixed page workers,
  pagination, retry/backoff, 429 `Retry-After`, timeouts, and schema drift.
- Normalization tables covering every value and drift case in the Spec.
- Database assertion that searches create no catalog or library rows.
- Profile-scope tests proving identical filters do not cross profile indexes.
- A 100,000-record synthetic benchmark that asserts correct output and records a
  generous regression ceiling or complexity ratio rather than a workstation-
  specific microbenchmark.
- OpenAPI tests for `202`, `404`, `410`, `422`, nullable totals, and warnings.

## Completion criteria

- Every JE-005 acceptance criterion has deterministic automated coverage.
- A live smoke test is optional and separately marked; CI never depends on the
  public provider.
- Backend lint, full tests, migration checks, and shutdown-with-active-search
  tests pass.
- No search result or cache metadata is persisted.

