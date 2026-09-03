# JE-007 — Multi-Provider Live Search Fan-In Specification

## Status

Proposed for Batch 03. Depends on JE-005 for the progressive search contract and
the in-memory index lifecycle. Adding providers must not persist provider
results, and V1 remains a single backend process.

## Purpose

Search several providers at once behind one provider-neutral request so a
profile sees roles that no single board carries. Himalayas, RemoteOK, and Jobicy
stream into one per-profile in-memory index that keeps the JE-005 progressive
semantics intact.

## Provider registry

Enabled providers are configuration, not code. The registry is built at startup
from `PROVIDER_CONFIG_JSON`, already defined in application settings and
currently unread. Each entry names a provider `key` matching the adapter's `key`
attribute and carries that adapter's own options, such as concurrency and
timeout.

| Field | Shape | Meaning |
| --- | --- | --- |
| `key` | string matching a registered adapter | Provider identity used in results, warnings, and saved snapshots |
| `enabled` | boolean, default true | Whether the adapter participates in searches |
| `options` | object | Adapter-specific settings such as concurrency and timeout |

An unknown key, a malformed entry, or a configuration that enables no provider
fails at startup with a clear message. Absent configuration falls back to the
documented default set. Provider keys are stable strings; they appear in
`JobResult.provider` and in `saved_jobs.provider`, so renaming a key is a
breaking change.

## Fan-in and progress semantics

A search consumes every enabled provider's `pages()` stream concurrently into
one search state:

- Normalized items from any provider are appended as they arrive, and existing
  local filtering, canonical filter keys, warm-index reuse, stale-while-refresh,
  and eviction behave exactly as specified by JE-005.
- `progress` is aggregate, monotonic, and weighted per provider. It never
  decreases when a slower provider revises its expected page count upward.
- `checked_count` is the sum of items examined across providers.
- `total` remains `null` and the final deterministic sort is withheld until
  every participating provider has finished or failed.
- The provider contract admits bulk providers that return their whole result set
  in one batch. A `total_pages` of 1 is legal, and progress weighting must not
  assume comparable page counts across providers.

Ordering across providers is deterministic once complete: the final sort is the
requested `newest`, `salary`, or `relevance` order, with a documented stable
tiebreak so two providers returning equally ranked roles produce the same page
on every run.

## Index memory budget

Retention limits are global, not per search. `SEARCH_MAX_ITEMS` caps the total
items held across every live state and `SEARCH_MAX_STATES` caps the number of
states; both are enforced by the eviction pass. Every retained item also holds
its raw provider payload for library snapshot creation, so the true footprint of
an item is larger than its search JSON.

Fan-in multiplies the items an index holds by roughly the number of enabled
providers. Inherited single-provider defaults would therefore make eviction
discard warm indexes that are still in use, regressing the JE-005 warm-index
design without any provider having failed.

- Item and state budgets are re-derived for the enabled provider count rather
  than inherited, and are documented alongside the other deployment settings.
- The derivation starts from a measured per-item footprint that includes the
  retained raw payload, not from an assumed item size.
- Eviction remains age-and-budget based. Fan-in must never let an in-progress
  search evict itself, its own not-yet-complete siblings, or the stale index a
  refresh is still serving.
- Consolidation under JE-008 reduces retained items and relaxes this pressure;
  the budgets are derived for the unconsolidated case so JE-007 stands alone.

## Per-provider status

Search responses carry a per-provider status block in addition to the existing
free-text `warnings` list:

```json
{
  "search_id": "uuid",
  "status": "complete",
  "progress": 1.0,
  "checked_count": 1840,
  "providers": [
    {"provider": "himalayas", "status": "complete", "progress": 1.0, "checked_count": 900},
    {"provider": "remoteok", "status": "complete", "progress": 1.0, "checked_count": 940},
    {"provider": "jobicy", "status": "failed", "progress": 1.0, "checked_count": 0}
  ],
  "is_partial": true,
  "warnings": ["jobicy: provider unavailable"]
}
```

Each provider entry reports `loading`, `complete`, or `failed`. `is_partial` is
true when the search finished while at least one provider failed.

## Partial provider failure

One provider failing is a partial result, not a failed search. The search still
reaches `complete`, results already accepted from healthy providers remain
readable, and the failing provider is named in its status entry and in a
sanitized warning. A search is `failed` only when every participating provider
fails. Failures never create database rows, and no provider failure aborts
another provider's in-flight work.

## RemoteOK adapter

RemoteOK returns its listings as one bulk JSON array. The first element is a
legal and attribution notice rather than a job and must be skipped. RemoteOK's
attribution and backlink requirement is preserved in every normalized result and
in anything the frontend renders. Normalization maps the provider's identity,
position, company, location, tag, salary, and epoch timestamp fields into
`JobResult`, annualizing compensation the way the Himalayas adapter does and
resolving both an original job URL and an application URL.

Because the response is not paginated, the adapter yields its results as one or
more bounded batches from a single request and reports an honest `total_pages`.

## Jobicy adapter

Jobicy exposes a remote-jobs endpoint with a documented per-request result cap
and upstream `geo`, `industry`, and `tag` parameters. The adapter maps
provider-neutral filters onto those parameters where the semantics match and
applies the remainder locally, following the JE-005 rule that unsupported
filters are applied after normalization.

The specification does not assume Jobicy returns an unbounded result set. The
adapter states the cap it observes, and when the cap truncates coverage for a
broad search the adapter emits a sanitized warning rather than presenting a
truncated set as complete.

## Adapter discipline

Both new adapters follow the conventions the Himalayas adapter established:
a bounded worker pool rather than one task per page, capped retry and backoff
for 429, timeout, and transient server responses honoring `Retry-After`,
per-request failures surfaced as warnings instead of hard failures where results
were already collected, description sanitization through the shared sanitizer,
and no logging of secrets, payloads, or response bodies. Raw accepted objects
stay internal and remain available for library snapshot creation.

## Out of scope

- Cross-provider duplicate detection and consolidation
- Frontend presentation of provider sources or per-provider status
- Persisting provider catalogs, search indexes, or provider health history
- Scheduled background ingestion and operational sync APIs
- Multi-instance or distributed search coordination
- Provider-specific ranking, AI ranking, or semantic search

## Acceptance criteria

1. Enabled providers are resolved from `PROVIDER_CONFIG_JSON`, and an unknown
   key, malformed entry, or empty enabled set fails at startup with a clear
   message.
2. A single search fans in across every enabled provider and merges normalized
   results into one profile-scoped in-memory index.
3. Aggregate `progress` is monotonic and `total` stays `null` until every
   participating provider finishes or fails.
4. A provider that returns its whole result set in one batch participates
   correctly, and progress weighting does not assume equal page counts.
5. One provider failing yields `status` `complete` with `is_partial` true, a
   named provider status entry, a sanitized warning, and retained results from
   healthy providers; all providers failing yields `failed`.
6. RemoteOK and Jobicy pagination, identity, compensation, employment,
   timestamps, and attribution normalize through contract tests against recorded
   responses.
7. Completed multi-provider searches sort deterministically, including a stable
   tiebreak across providers.
8. Item and state budgets are re-derived from a measured per-item footprint for
   the enabled provider count and documented for deployment, and a warm default
   index survives fan-in across every enabled provider without being evicted by
   the added volume alone.
9. No multi-provider search creates or updates a PostgreSQL row, and JE-005
   reuse, refresh, warming, eviction, and shutdown behavior is unchanged.
