# JE-007 — Multi-Provider Live Search Fan-In Implementation Plan

Implements
[`JE-007-multi-provider-search-fan-in.md`](../specs/JE-007-multi-provider-search-fan-in.md)
on top of the completed JE-005 search runtime.

## Implementation baseline — reuse, do not rebuild

| Existing work | Current evidence | Disposition |
| --- | --- | --- |
| `providers/protocol.py` | `ProgressiveProvider` protocol and `ProviderPageBatch` already provider-neutral | Retain; extend only for bulk single-batch providers and per-provider status |
| `providers/himalayas.py` | Bounded page workers, retry/backoff, live-verified normalization | Retain unchanged; use as the reference implementation for the two new adapters |
| `providers/sanitize.py` | HTML stripping for descriptions | Reuse in both new adapters |
| `search/live.py` | Reuse window, stale-while-refresh, promotion, local filters, final sort, TTL eviction, `resolve_job` | Extend `_populate` and progress accounting only; do not rewrite lifecycle, reuse, or eviction |
| `config.py` `provider_config` | `PROVIDER_CONFIG_JSON` setting defined but never read | Activate as the registry source |
| `main.py` lifespan | Constructs one `HimalayasProvider` and one manager | Refactor to build a registry and pass every enabled adapter |
| `schemas/discovery.py` | `SearchPage`, `SearchRefreshPage`, `JobResult` | Extend with the per-provider status block and `is_partial` |
| `tests/helpers/fake_provider.py` | Single fake progressive provider | Extend to multi-provider fixtures with uneven and bulk page shapes |

The JE-005 suite passes today: `test_live_search_manager.py`,
`test_live_search_lifecycle.py`, `test_search_api.py`,
`test_search_no_persistence.py`, `test_himalayas_http.py`, and
`test_himalayas_normalization.py`. Every assertion that describes
single-provider behavior must keep passing or be extended deliberately, never
deleted to accommodate fan-in. Ruff and the benchmark marker configuration are
unchanged.

## Remaining implementation

### Provider registry and configuration

1. Add a registry module that maps provider keys to adapter factories and builds
   the enabled adapter list from `settings.provider_config`. Do not revive
   `ingestion/registry.py`; that surface belongs to the superseded Batch 01
   runtime.
2. Validate configuration at startup. Reject unknown keys, malformed entries,
   and a configuration that leaves no provider enabled, with a message naming
   the offending key.
3. Define the default set used when configuration is absent, and document it
   alongside the other environment variables so a deployment can disable a
   failing provider without a code change.
4. Pass adapter options through the registry rather than reading settings inside
   each adapter, keeping per-provider concurrency and timeout configurable.
5. Update the lifespan to construct the registry, hand every adapter to one
   `LiveSearchManager`, and close all adapters on shutdown. Startup must not
   block on provider reachability.

### Fan-in and progress

1. Change the manager to hold an ordered collection of providers and to consume
   their `pages()` streams concurrently into one `SearchState`, appending items
   under the existing lock discipline.
2. Track expected and completed work per provider, then derive aggregate
   progress from those totals so a slow provider revising its page count upward
   cannot make progress regress.
3. Keep `total` null and withhold the final sort until every provider has
   reached a terminal state. Sum `checked_count` across providers.
4. Record per-provider status, progress, checked count, and warnings on the
   state, and expose them through `SearchPage` and `SearchRefreshPage` with an
   `is_partial` flag.
5. Treat one provider's exhaustion or failure as terminal for that provider
   only. Cancel sibling work only on search cancellation or shutdown, never on a
   single provider's failure.
6. Add a stable tiebreak to the final sort so equally ranked results from
   different providers page deterministically.
7. Confirm `resolve_job` still resolves authoritatively by provider and provider
   job ID now that identities from several providers share one index.

### RemoteOK and Jobicy adapters

1. Implement the RemoteOK adapter against its bulk array response. Skip the
   leading legal notice element, carry attribution and the required backlink
   into the normalized result, and yield bounded batches with an honest
   `total_pages`.
2. Implement the Jobicy adapter against its remote-jobs endpoint, mapping
   provider-neutral filters onto the supported `geo`, `industry`, and `tag`
   parameters and applying the rest locally.
3. Verify both live contracts before finalizing normalization tables, and record
   the observed identity field, timestamp shape, salary period, employment
   values, and result cap in the adapter module rather than assuming the
   documented contract.
4. Emit a sanitized warning when Jobicy's per-request cap truncates coverage for
   a broad search instead of reporting a truncated set as complete.
5. Reuse the Himalayas retry, backoff, `Retry-After`, and bounded-worker
   discipline in both adapters, and route every description through the shared
   sanitizer.
6. Preserve raw accepted objects internally for library snapshot creation
   without returning them in search JSON.

## Test plan

- Multi-fake-provider fan-in tests covering interleaved batches, uneven page
  counts, one bulk provider alongside one paginated provider, and out-of-order
  completion.
- Aggregate progress tests asserting monotonicity when a provider revises its
  expected page count upward, and null totals until the last provider finishes.
- Partial-failure tests distinguishing one provider failing (`complete` with
  `is_partial` true and retained results) from every provider failing
  (`failed`).
- Registry tests for unknown keys, malformed entries, an empty enabled set, the
  absent-configuration default, and disabling a provider by configuration alone.
- HTTP-mocked RemoteOK and Jobicy tests for request parameters, retry and
  backoff, 429 `Retry-After`, timeouts, and schema drift, plus normalization
  tables covering every value case in the Spec including the RemoteOK legal
  element and the Jobicy cap warning.
- Determinism tests proving identical inputs delivered in different provider
  arrival orders produce identical completed pages.
- A database assertion that a multi-provider search creates no catalog or
  library rows, and profile-scope tests proving indexes still do not cross
  profiles.
- Separately invoked live smoke tests for both new providers, marked so CI never
  depends on a public provider.

## Completion criteria

- Every JE-007 acceptance criterion has deterministic automated coverage using
  fake providers or recorded responses.
- `./ci.sh lint` and `./ci.sh test` pass, the existing JE-005 suite still passes,
  and the 100,000-record benchmark shows no regression from fan-in.
- The OpenAPI schema documents the per-provider status block and `is_partial`,
  and the configured provider set is documented for deployment.
- No deduplication, frontend, scheduling, persistence, or multi-instance
  behavior is added.
