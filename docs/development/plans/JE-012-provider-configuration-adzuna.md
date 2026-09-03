# JE-012 — Provider Configuration and Adzuna Implementation Plan

Implements
[`JE-012-provider-configuration-adzuna.md`](../specs/JE-012-provider-configuration-adzuna.md)
after the Batch 04 ranking work, so the added result volume arrives into a
working relevance sort.

## Implementation baseline — reuse, do not rebuild

| Existing work | Current evidence | Disposition |
| --- | --- | --- |
| `providers/registry.py` | `KNOWN_KEYS`, `DEFAULT_ENABLED`, `PROVIDER_DISPLAY_NAMES`, `_factory`, `build_providers`, `enabled_provider_count` | Extend with credential requirements and state resolution; keep the existing startup failures |
| `providers/protocol.py` | `ProgressiveProvider`, `ProviderPageBatch` | Unchanged; the Adzuna adapter implements it as-is |
| `providers/himalayas.py` | Bounded worker pool, capped retry and backoff, `Retry-After`, warning discipline | Follow as the adapter pattern |
| `providers/remoteok.py`, `providers/jobicy.py` | Bulk and capped-endpoint adapters, warning on truncation | Follow for warning phrasing and normalization conventions |
| `providers/sanitize.py` | Shared description sanitizer | Reuse; add no second sanitizer |
| `normalization/compensation.py` | Annualization | Reuse for Adzuna salary fields |
| `config.py` | `Settings`, `provider_config`, `effective_search_max_items` | Add Adzuna credential settings; feed state resolution into the budget derivation |
| `api/providers.py` | `GET /providers` sourced from live adapters | Extend to report state including unconfigured providers |
| `schemas/discovery.py` | `ProviderDescriptor` | Add `state`; keep it credential-free |

JE-007 and JE-008 provider suites pass today. Existing adapter behavior must not
change.

## Remaining implementation

### Registry and configuration

1. Declare required credentials per provider as registry data, so a new
   credentialed provider is a data addition rather than a branch.
2. Add a resolution function returning each known provider's state, and build
   only `enabled` providers.
3. Feed the count of `enabled` providers into `effective_search_max_items` so an
   unconfigured provider does not inflate the memory budget.
4. Keep unknown keys, malformed entries, and an empty enabled set as startup
   failures; make a missing credential explicitly not one.
5. Add Adzuna settings for `app_id`, `app_key`, and default country, with no
   defaults for the secrets, and document them alongside the other deployment
   settings.

### Adzuna adapter

1. Implement `providers/adzuna.py` against the unchanged `ProgressiveProvider`
   protocol with a bounded worker pool and honest `total_pages`.
2. Map `country` onto the per-country endpoint, falling back to the configured
   default, and record the queried country in the result provenance.
3. Map query, location, minimum salary, employment type, and recency onto
   documented upstream parameters; leave everything else to JE-011 index
   filtering.
4. Normalize identity, title, company, location, contract type and time, salary
   range and currency, timestamps, and both URLs, annualizing through the shared
   module and sanitizing descriptions through the shared sanitizer.
5. Preserve Adzuna attribution on every normalized result.
6. Implement the per-search request budget, ending the stream with a sanitized
   quota warning on budget exhaustion or upstream quota rejection, and keep
   retry and backoff off the quota path.
7. Log no credential, payload, or response body.

### API surface

1. Add `state` to `ProviderDescriptor` and report every known provider from
   `GET /providers`, sourcing enabled entries from the live adapters and the
   remainder from the resolved registry view.
2. Assert by test that no credential value appears in any response or log.

## Test plan

- Registry tests for each state, including enabled-but-missing-credential
  resolving to `unconfigured` and startup succeeding.
- A test that JE-007's three startup failure modes still fail.
- Budget derivation test proving an unconfigured provider does not change
  `effective_search_max_items`.
- Adzuna contract tests against recorded responses: pagination, identity,
  compensation annualization with currency, contract mapping, timestamps, both
  URLs, and attribution.
- Country selection tests for an explicit filter, an empty filter, and the
  queried country being discoverable.
- Quota tests for budget exhaustion and upstream quota rejection, asserting a
  sanitized warning, `complete` with `is_partial` true, and retained results
  from other providers.
- Retry and backoff tests honoring `Retry-After` and not retrying quota
  rejections.
- A credential-leak test scanning responses and captured logs.
- `GET /providers` tests covering all three states.
- Re-run of JE-005, JE-007, JE-008, and JE-011 suites unchanged.

## Completion criteria

- Every JE-012 acceptance criterion has deterministic automated coverage.
- `./ci.sh lint` and `./ci.sh test` pass against a real PostgreSQL database.
- A deployment without Adzuna credentials starts and searches normally, proven
  by test rather than by inspection.
- No credential is logged or exposed, no Adzuna result is persisted, and no
  second sanitizer, annualizer, or provider protocol is introduced.
