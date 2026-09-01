# 001 — Normalized Job Model Specification

## Status

Proposed for V1. This specification is the source of truth for the normalized job
record used by ingestion and the read API.

## Purpose

Every provider must be converted into one provider-neutral record before it can
be stored or searched. The model must preserve the source listing, support the V1
filters, and remain useful when a provider omits optional data.

## Requirements

### Identity and provenance

- `id` is an application-generated UUID and is the public job identifier.
- `provider` is a stable lowercase key containing letters, digits, `_`, or `-`.
- `provider_job_id` is the provider's stable identifier for the posting.
- `(provider, provider_job_id)` is unique. Re-fetching that identity updates the
  existing row; it never creates a second row.
- `raw_payload` stores the most recently accepted provider object as JSON. It is
  internal diagnostic data and is never returned by the public jobs API.
- `job_url` is the canonical source listing URL and is required. `apply_url` is
  nullable and may differ from `job_url`.

Provider identity is the only duplicate guarantee in this batch. Similar jobs
from different providers remain separate records.

### Core content

The model contains:

| Field | Required | Meaning |
| --- | --- | --- |
| `title` | yes | Provider-supplied job title after whitespace cleanup |
| `company` | yes | Provider-supplied display company name |
| `description` | no | Plain text or sanitized provider description |
| `employment_type` | yes | Normalized employment classification |
| `remote_type` | yes | Normalized workplace classification |

`title`, `company`, `provider`, `provider_job_id`, and `job_url` must be non-empty
after trimming. Display text is not case-normalized.

Allowed `employment_type` values are `full_time`, `part_time`, `contract`,
`temporary`, `internship`, `other`, and `unspecified`. Allowed `remote_type`
values are `remote`, `hybrid`, `on_site`, and `unspecified`. Providers use
`unspecified` when they cannot support a more precise mapping.

### Location and eligibility

- `location_text` preserves the provider's display location.
- `city`, `region`, and `country_code` are nullable structured components.
- `country_code` and every value in `eligible_country_codes` use uppercase ISO
  3166-1 alpha-2 codes.
- `eligible_country_codes = null` means eligibility is unknown.
- `eligible_country_codes = []` means the provider explicitly describes the job
  as worldwide.
- A non-empty `eligible_country_codes` array is the explicit set of eligible
  countries. Values are unique and sorted before persistence.

Physical location and applicant eligibility are independent. A remote job may
have no physical country while still having explicit eligibility restrictions.

### Compensation

The source compensation is represented by nullable `salary_min`, `salary_max`,
`salary_currency`, and `salary_period` fields. Allowed periods are `hourly`,
`daily`, `weekly`, `monthly`, `yearly`, and `other`.

- Amounts are positive decimal values with two fractional digits of storage
  precision; floating-point values are not used for persistence.
- If both bounds exist, `salary_min <= salary_max`.
- A source amount requires an uppercase ISO 4217 `salary_currency` and a period.
- `salary_min_annual` and `salary_max_annual` are derived comparable values in
  the same currency. They are never currency-converted.
- Annualization uses 2,080 hours, 260 days, 52 weeks, or 12 months per year.
- `yearly` values are unchanged. `other` values are preserved but are not
  annualized.
- Missing periods are not guessed. In particular, a large periodless value is
  not assumed to be annual compensation.

All compensation fields are null when the provider does not state compensation.

### Lifecycle and timestamps

Allowed `status` values are `active` and `inactive`.

- New jobs start as `active`.
- `posted_at` is the provider's timezone-aware publication timestamp, if known.
- `discovered_at` is set once when the identity is first accepted.
- `last_seen_at` is the last successful provider run that contained the identity.
- `updated_at` changes whenever persisted normalized content changes.
- `inactive_at` is set when an active job becomes inactive and cleared when the
  job is rediscovered.
- All timestamps are stored in UTC using timezone-aware database columns.

The ingestion specification owns the rules for transitioning between lifecycle
states. Normal job searches include only active jobs; direct detail lookup can
show an inactive job.

## Data integrity

The database must enforce the unique provider identity, positive compensation,
ordered salary ranges, valid lifecycle states, and non-empty required strings.
Application validation must additionally enforce provider-key syntax, ISO codes,
URL shape, sorted unique eligibility codes, and timestamp awareness.

Deletes are not part of normal ingestion. Retaining inactive rows preserves
stable public identifiers and source history.

## Out of scope

- Cross-provider duplicate matching or canonical job groups
- Companies as a separate entity
- Currency conversion or exchange-rate storage
- Tax, equity, bonus, and total-compensation modeling
- Skill extraction, semantic embeddings, or AI-derived fields
- Application tracking and automation

## Acceptance criteria

1. The schema can store every field required by the V1 goal without retaining
   provider-specific columns.
2. Two records cannot share a provider identity, while equivalent postings from
   different providers can coexist.
3. Unknown, worldwide, and explicitly restricted eligibility remain distinct.
4. Source compensation remains visible while only recognized periods produce
   annualized values.
5. Invalid salary ranges, non-positive salary values, and empty required fields
   are rejected before or by persistence.
6. A job can transition active → inactive → active without changing `id` or
   `discovered_at`.
7. Raw payloads are stored internally but are absent from public job schemas.

