# JE-005 — Live Provider Search and Himalayas Specification

## Status

In progress for Batch 02. Depends on JE-004 for profiles and default search
preferences. Search execution itself must not persist provider results.

## Purpose

Search external providers live, progressively expose useful partial results, and
keep warm per-profile indexes in backend memory. PostgreSQL is reserved for the
personal library defined by JE-004.

## Search filters

The provider-neutral request supports:

| Field | Shape | Meaning |
| --- | --- | --- |
| `query` | trimmed string, max 200 | Keywords sent upstream where supported |
| `country` | nullable country name/code | Eligibility/location restriction |
| `worldwide` | nullable boolean | Include or exclude worldwide roles |
| `seniority` | list of strings | OR within seniority |
| `employment_types` | list of strings | OR within employment type |
| `minimum_salary` | nullable non-negative integer | Annual salary threshold applied locally |
| `posted_within_days` | nullable integer, 1–3650 | Posting recency applied locally |
| `sort` | enum | `relevance`, `newest`, or `salary` |

Supported filters are pushed upstream. The backend fetches the complete matching
provider result set, normalizes it, applies remaining filters, and performs the
final deterministic sort. Exact totals and final ordering exist only after the
search completes.

## Progressive search API

### `POST /searches`

Accepts `profile_id` and optional filters. Missing filters use that profile's
default preferences. Returns `202` with the first search snapshot and starts
background loading in the application process.

### `GET /searches/{search_id}`

Requires the owning `profile_id` and accepts one-based `page` and `page_size`
from 1 through 100. A search belonging to another profile answers `404`.
A response contains:

```json
{
  "search_id": "uuid",
  "status": "loading",
  "progress": 0.4,
  "checked_count": 800,
  "items": [],
  "page": 1,
  "page_size": 25,
  "total": null,
  "is_complete": false,
  "warnings": []
}
```

`status` is `loading`, `complete`, or `failed`. While loading, pages may contain
partial results, progress is monotonic, and `total` is null. When complete,
`progress` is 1, `total` is exact, and all pages use final sorting. If a later
provider page fails, already accepted results remain available and the response
contains a safe warning; failures do not create database rows.

### `POST /profiles/{profile_id}/default-search/refresh`

Starts a forced refresh for the profile's current default preferences. A
compatible completed index remains readable while refresh runs. The endpoint
returns the new search identity and enough state for the UI to keep showing the
stale result until the replacement is useful.

## In-memory index lifecycle

- One backend process owns all search state in V1.
- Search indexes are scoped by profile and canonical filters.
- Compatible recent searches may be reused instead of refetched.
- Default searches are warmed asynchronously at application startup.
- Forced refresh uses stale-while-refresh behavior.
- Completed, failed, and abandoned searches have bounded retention by age and
  total memory; eviction makes their IDs return `410`.
- Application shutdown cancels work and closes HTTP clients cleanly.

Multiple backend replicas, distributed cache coordination, and durable search
recovery are deferred. Deployment documentation must state the single-process
constraint.

## Himalayas adapter

The first provider uses `https://himalayas.app/jobs/api/search`, one-based pages,
and the provider's returned page size. Concurrency is configurable and bounded;
429, timeout, and transient server responses use capped retry/backoff honoring
`Retry-After`. Secrets, complete payloads, and response bodies are not logged.

Normalization must accommodate the verified live contract:

- stable identity is `guid` (currently an application URL);
- `pubDate` and similar timestamps may be Unix seconds, milliseconds, or an RFC
  3339 string;
- `locationRestrictions` may contain country-name strings or documented objects
  containing alpha-2 codes;
- `seniority` may be a list;
- empty logo URLs normalize to null;
- salary periods include `hourly`, `weekly`, `fortnightly`, `monthly`, and
  `annual`; `fortnightly` annualizes by 26 and `annual` maps to yearly;
- employment maps Full Time, Part Time, Contractor, Temporary, Intern,
  Volunteer, and Other explicitly;
- Himalayas listings are normalized as remote;
- upstream sort values are `relevant`, `recent`, and `salaryDesc` for the three
  provider-neutral sorts;
- public results include clear Himalayas attribution and original links.

Provider HTML must be sanitized before presentation or rendered as text. Raw
accepted objects remain internal and are available only for JE-004 snapshot
creation.

## Performance expectation

Network concurrency, not CPU count, is the principal upstream constraint. Local
filtering/sorting may use worker threads or optimized data structures when
measurements justify them. A repeatable 100,000-item synthetic benchmark must
guard against accidental quadratic behavior without asserting a brittle
machine-specific duration.

## Out of scope

- Persisting provider catalogs or search indexes
- Multi-instance or distributed search coordination
- Cross-provider deduplication
- AI ranking, semantic search, resume matching, or automated applications
- Scheduled background ingestion

## Acceptance criteria

1. Searches return partial pages with monotonic progress and null totals before
   completion, then exact totals and deterministic sorting.
2. No ordinary search creates or updates a PostgreSQL job row.
3. Searches and warm indexes remain scoped to the requesting profile.
4. A refresh keeps a compatible completed result usable until replacement.
5. Himalayas pagination, live response variants, compensation, employment, and
   timestamps normalize through contract tests.
6. Provider throttling and transient failure are bounded, safe, and retain
   already collected results.
7. Startup warming, eviction, and shutdown cleanup are tested.
8. Local filtering/sorting handles 100,000 synthetic records without quadratic
   regression.

