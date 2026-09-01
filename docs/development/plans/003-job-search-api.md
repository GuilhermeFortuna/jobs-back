# 003 — Job Search API Implementation Plan

Implements [`003-job-search-api.md`](../specs/003-job-search-api.md) after Plan
001. Plan 002 supplies production data later but is not a code dependency of the
read path.

## Approach

Create a dedicated jobs router and query service rather than adding domain logic
to `main.py`. Keep request validation, query construction, and response mapping
separate so filter semantics can be unit- and integration-tested independently.

### Database search support

1. Add an Alembic revision with a GIN expression index over an English-weighted
   `to_tsvector` built from title, company, and description. The SQLAlchemy query
   must use the identical expression so PostgreSQL can use the index.
2. Add supporting B-tree indexes only where query plans demonstrate value,
   starting with status/provider, status/remote type, status/employment type,
   status/posting time, and currency/annual salary fields from Plan 001.
3. Use `websearch_to_tsquery` for `q` and parameterized SQLAlchemy expressions
   for every filter. Do not interpolate query values or sort expressions.
4. Use one filtered count query and one bounded item query. Normalize repeated
   values before constructing predicates.

### API and query service

1. Add Pydantic request parsing for query strings with explicit maximum lengths,
   ISO normalization, range validation, and the salary/currency dependency.
2. Add `JobSummary`, `JobDetail`, and `JobPage` response schemas matching the
   Spec. Map allowed fields explicitly from ORM rows.
3. Implement filter predicates with OR within repeated values and AND across
   filter categories. Implement eligibility as explicit array membership OR an
   explicitly empty array; null remains unknown and does not match.
4. Implement annual salary overlap with effective lower/upper bounds. For salary
   sorting, retain null-salary jobs last, exclude other known currencies, and use
   the required UUID tie-breaker.
5. Add a router for `GET /jobs` and `GET /jobs/{job_id}` and include it from
   `create_app()`. Keep the existing `/health` behavior unchanged.
6. Return standard FastAPI validation errors and the exact not-found detail from
   the Spec. Do not catch database or programming errors as `404`/`422`.

Offset calculation uses `(page - 1) * page_size`. `total_pages` is zero when
`total` is zero; otherwise it is the ceiling of `total / page_size`.

## Legacy reuse assessment

Reference project: `job-tracker/backend/src/job_tracker`.

| Legacy code | Disposition | Reason |
| --- | --- | --- |
| `jobs.py` filter and paging test cases | Reference | Useful boundary cases for page size, currency requirements, summary/detail separation, and missing IDs |
| `jobs.py` SQL and in-memory text scan | Exclude | SQLite-specific, non-scalable, and lacks the required filters and sorts |
| `server.py` response payload helpers | Reference selectively | Check established field intent, but define new typed schemas and routes instead of porting the monolith |
| `tests/test_http_service.py` jobs cases | Adapt selectively | Retain transport-level success/error scenarios that match the new endpoint contract |
| Live source search routes and SSE code | Exclude | Search reads the normalized database only in this V1 batch |

No production module should import or mechanically mirror the legacy query or
server modules.

## Test plan

- Seed PostgreSQL with active/inactive jobs covering every enum, null location,
  worldwide/unknown/restricted eligibility, multiple providers and currencies,
  one-sided salaries, unknown periods, and tied timestamps/amounts.
- Test each filter alone, OR behavior within repeated filters, AND behavior across
  filters, and representative all-filter combinations.
- Test text matches in title, company, and description plus punctuation and empty
  queries.
- Test salary overlap boundaries, currency isolation, missing annual values,
  ascending/descending null placement, and every invalid salary combination.
- Test first, partial, exact-last, and past-end pages and deterministic tie order.
- Test active-only lists, inactive detail, unknown UUID, malformed UUID, every
  enum/ISO/pagination validation boundary, and raw-payload non-disclosure.
- Run `EXPLAIN` assertions or reviewed query plans for keyword search and the
  primary newest/salary paths against a representative generated dataset; avoid
  brittle exact-cost assertions.
- Retain the existing health test unchanged.

## Completion criteria

- Every paired Spec acceptance criterion has an API-level PostgreSQL test.
- OpenAPI documents both endpoints, all query parameters, enum values, response
  schemas, `404`, and `422` outcomes.
- Migration upgrade/downgrade, `./ci.sh lint`, and `./ci.sh test` pass.
- No frontend, facet, authentication, provider-fetch, or cross-provider dedup
  behavior is added.

