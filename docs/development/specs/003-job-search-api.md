# 003 — Job Search API Specification

## Status

Proposed for V1. Depends on the normalized model from Spec 001. Ingested data is
produced through Spec 002, but the read API does not depend on adapter code.

## Endpoints

### `GET /jobs`

Returns a deterministic page of active normalized jobs.

Supported query parameters:

| Parameter | Shape | Behavior |
| --- | --- | --- |
| `q` | one string, max 200 characters | Keyword search over title, company, and description |
| `location` | one string, max 200 characters | Case-insensitive match over display location, city, region, and country code |
| `remote_type` | repeated enum | Match any selected remote type |
| `eligible_country` | repeated ISO alpha-2 code | Match explicitly eligible or worldwide jobs; exclude unknown eligibility |
| `employment_type` | repeated enum | Match any selected employment type |
| `provider` | repeated provider key | Match any selected provider |
| `posted_after` | one RFC 3339 timestamp | Include jobs posted at or after the timestamp; jobs without `posted_at` do not match |
| `salary_min` | non-negative decimal | Lower boundary of the user's desired annual range |
| `salary_max` | non-negative decimal | Upper boundary of the user's desired annual range |
| `salary_currency` | ISO 4217 code | Currency used for salary comparison or sorting |
| `sort` | enum | `newest` (default), `salary_asc`, or `salary_desc` |
| `page` | integer, default 1 | One-based page number |
| `page_size` | integer, default 20 | Number of jobs, from 1 through 100 |

Repeated parameters use repeated keys, for example
`remote_type=remote&remote_type=hybrid`. An empty selection has no filtering
effect. Duplicate values are accepted and treated once.

Keyword search uses PostgreSQL web-search syntax over a stored English text
search vector. Malformed web-search punctuation must not cause a server error.
Keyword relevance is not a sort option in V1.

Eligibility matching includes an explicit country code or an explicitly
worldwide empty list. It excludes null/unknown eligibility. `location` and
`eligible_country` are independent filters.

Salary bounds describe a desired range and match jobs whose normalized annual
range overlaps it. A one-sided listing range uses its known bound for both ends.
Salary filtering:

- requires `salary_currency`;
- excludes jobs without an annualized amount;
- compares only jobs in that currency;
- rejects `salary_min > salary_max`.

Salary sorting also requires `salary_currency`. It excludes jobs with a
different known currency, sorts comparable jobs first, and places jobs with no
annualized compensation last. Ascending order uses the effective lower bound;
descending order uses the effective upper bound.

`newest` sorts descending by `posted_at`, falling back to `discovered_at` when a
provider did not supply a posting timestamp. All sorts use `id` as a final stable
tie-breaker in the same direction as the primary sort.

The response uses snake_case JSON:

```json
{
  "items": [],
  "page": 1,
  "page_size": 20,
  "total": 0,
  "total_pages": 0
}
```

Requesting a page past the end returns `200` with an empty `items` array and the
real pagination metadata.

### `GET /jobs/{job_id}`

Returns one job by UUID. Unlike the list endpoint, it can return an inactive job
so an existing link can explain that the source listing is no longer active.
Unknown IDs return `404` with `{"detail": "Job not found"}`. A malformed UUID is
a `422` validation error.

## Response fields

Every list item contains:

- identity, `status`, provider, provider job ID;
- title, company, location fields, eligibility countries;
- remote type and employment type;
- source and annualized salary fields;
- job URL and nullable apply URL;
- posted, discovered, and last-seen timestamps.

The detail response adds `description`, `updated_at`, and `inactive_at`. It never
contains `raw_payload`.

Dates use RFC 3339 UTC timestamps. Decimal amounts serialize as JSON numbers.
Enums and field semantics match Spec 001 exactly.

## Validation and errors

Unknown enum values, invalid ISO codes, invalid timestamps, negative salary
bounds, oversized text queries, and invalid pagination return FastAPI's standard
`422` response. Salary filters or salary sorting without `salary_currency` also
return `422` with an error attached to `salary_currency`.

The endpoints are public and read-only in V1. They use the application's existing
CORS configuration and add no authentication behavior.

## Out of scope

- Facet counts or filter-option endpoints
- Relevance, popularity, or AI ranking
- Currency conversion
- Cursor pagination
- Saved searches and user-specific state
- Starting provider sync from the API
- Cross-provider consolidated responses

## Acceptance criteria

1. Every V1 filter can be applied alone and in combination with every other
   filter.
2. Multi-select filters use OR within one field and AND across different fields.
3. Pagination metadata is correct for empty, partial, full, and past-end pages.
4. Newest and salary orders are deterministic when primary values tie or are
   missing.
5. Salary filtering never compares different currencies or unannualized values.
6. Lists exclude inactive jobs while detail lookup can return them.
7. Invalid input produces `422`, unknown valid UUIDs produce `404`, and neither
   endpoint exposes raw provider payloads.

