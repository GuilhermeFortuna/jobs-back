# JE-012 — Provider Configuration and Adzuna Adapter Specification

## Status

Proposed for Batch 04. Depends on JE-007 for the provider registry, fan-in, and
partial-failure semantics. Governed by
[ADR-002](../decisions/ADR-002-skill-based-relevance-and-provider-credentials.md),
which separates a provider being configured from a provider being enabled.

## Purpose

Admit providers that require credentials, and add Adzuna as the first of them.
Every adapter to date runs key-less, so an enabled provider is assumed to be
usable. Adzuna needs an application id and key and enforces a free-tier request
quota, both of which the registry currently has no way to express.

## Configured versus enabled

A provider declares the credentials it requires. The registry resolves three
states:

| State | Meaning | Participates in search |
| --- | --- | --- |
| `enabled` | Enabled by configuration and holding every credential it requires | Yes |
| `unconfigured` | Enabled by configuration but missing at least one required credential | No |
| `disabled` | Disabled by `PROVIDER_CONFIG_JSON` | No |

Rules:

- A missing credential must not fail startup. A key-less deployment starts,
  serves searches from the providers it can use, and reports the rest as
  unconfigured. JE-007's startup failures for an unknown key, a malformed entry,
  and an empty enabled set are unchanged.
- An unconfigured provider is not constructed, does not participate in fan-in,
  contributes no provider status entry to a search, and does not count toward
  the fan-in memory budget derivation.
- Credentials are read from settings. They are never logged, never included in
  a warning, and never returned by any endpoint.

`GET /providers` reports state so a client cannot offer a filter for a provider
that will never answer:

```json
[
  {"key": "himalayas", "display_name": "Himalayas", "state": "enabled"},
  {"key": "adzuna", "display_name": "Adzuna", "state": "unconfigured"}
]
```

The endpoint continues to source enabled providers from the live adapters the
manager holds. Unconfigured providers are reported from the registry's resolved
view, with no credential detail.

## Adzuna adapter

Adzuna exposes a paginated JSON search API scoped by country, requiring
`app_id` and `app_key` query credentials.

- **Country scoping.** The API is per-country. The adapter maps the
  provider-neutral `country` filter onto the request path and falls back to a
  configured default country when the filter is empty. It states the country it
  queried in its results' provenance and does not silently query one country
  while the profile asked about another.
- **Filter mapping.** Query, location, minimum salary, employment type, and
  posting recency map onto documented upstream parameters where the semantics
  match. Everything else is applied locally after normalization, following the
  JE-005 rule and the JE-011 requirement that membership is decided in the
  index.
- **Normalization.** Provider identity, title, company, location, contract type
  and time, salary minimum and maximum with currency, posting timestamp,
  original job URL, and application URL map into `JobResult`. Compensation is
  annualized the way the existing adapters do. Descriptions pass through the
  shared sanitizer.
- **Attribution.** Adzuna's attribution requirement is preserved on every
  normalized result and in anything the frontend renders.
- **Pagination.** The adapter paginates with a bounded worker pool and reports an
  honest `total_pages`, following the Himalayas adapter's conventions.

## Quota handling

The free tier caps daily requests. The adapter carries an explicit request
budget for a single search, configurable through the provider's `options`.

- Reaching the budget, or receiving an upstream quota rejection, stops that
  provider's paging and completes its stream with a sanitized warning naming
  quota exhaustion.
- The search reaches `complete` with `is_partial` true and results from healthy
  providers retained, exactly as JE-007 specifies for partial failure. Quota
  exhaustion is never a failed search on its own.
- Retry and backoff for 429, timeout, and transient server responses follow the
  existing adapter discipline and honor `Retry-After`. Backoff must not be used
  to work around a quota rejection.

## Out of scope

- Remotive and We Work Remotely adapters — JE-013
- Frontend rendering of provider state — JE-014
- Persisting provider health, quota counters, or catalogs
- Credential management UI, secret rotation, or per-profile credentials
- Scheduled ingestion and multi-instance coordination

## Acceptance criteria

1. A provider declares its required credentials, and the registry resolves
   `enabled`, `unconfigured`, and `disabled` from configuration plus credential
   presence.
2. A deployment with no Adzuna credentials starts successfully, searches with
   the remaining providers, and reports Adzuna as `unconfigured`.
3. An unconfigured provider is not constructed, adds no provider status entry to
   a search, and does not change the derived fan-in memory budget.
4. JE-007's startup failures for unknown keys, malformed entries, and an empty
   enabled set still occur.
5. `GET /providers` reports state for every known provider and exposes no
   credential value; no log, warning, or response contains a credential.
6. With credentials present, Adzuna participates in fan-in and its results
   normalize correctly — identity, title, company, location, contract mapping,
   annualized compensation with currency, timestamps, both URLs, and attribution
   — proven by contract tests against recorded responses.
7. The `country` filter selects the queried country, an empty filter uses the
   configured default, and the queried country is discoverable from the result.
8. Reaching the request budget or an upstream quota rejection ends that
   provider's stream with a sanitized warning and yields `complete` with
   `is_partial` true, retaining other providers' results.
9. Retry and backoff honor `Retry-After` and are not used against quota
   rejections.
10. No Adzuna result is persisted, and JE-005, JE-007, JE-008, and JE-011
    behavior is otherwise unchanged.
