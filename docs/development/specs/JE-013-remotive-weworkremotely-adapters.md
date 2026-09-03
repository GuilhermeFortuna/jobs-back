# JE-013 — Remotive and We Work Remotely Adapters Specification

## Status

Proposed for Batch 04. Depends on JE-007 for the registry, fan-in, and
partial-failure semantics, on JE-008 for consolidation, and on JE-012 for the
provider state resolution both adapters register through. Both providers are
key-less. Governed by
[ADR-002](../decisions/ADR-002-skill-based-relevance-and-provider-credentials.md).

## Purpose

Widen coverage with two providers that carry roles the existing set misses,
behind the unchanged adapter contract. Overlap with existing providers is
resolved by JE-008 consolidation, not by this task.

## Remotive adapter

Remotive exposes a public JSON endpoint returning remote listings with category
and search parameters and a documented result cap per request.

- Supported filters map onto upstream parameters where the semantics match;
  everything else is applied locally after normalization.
- Normalization maps identity, title, company, category, tags, job type,
  candidate location text, salary text, publication timestamp, and the
  application URL into `JobResult`.
- Salary arrives as free text rather than structured numbers. The adapter parses
  what it can confidently annualize and leaves the fields null otherwise. It
  must not guess a currency, and it must not infer a range from a single figure.
- The response is not open-endedly paginated. The adapter states the cap it
  observes and, when the cap truncates coverage for a broad search, emits a
  sanitized warning rather than presenting a truncated set as complete.
- Remotive's attribution requirement is preserved on every normalized result.

## We Work Remotely adapter

We Work Remotely publishes RSS feeds rather than a JSON API, so this adapter
carries a parsing burden the others do not.

- The adapter consumes the published feeds, parses entries defensively, and
  treats a malformed entry as skippable rather than as a feed failure.
- Feed entries carry less structure than a JSON API. Title and company are
  frequently combined in one field and are separated by documented rules; region
  and category arrive as text. Fields that cannot be recovered confidently stay
  null rather than being guessed.
- Feed items carry no salary in a reliable structured form. Salary fields stay
  null unless a value can be parsed confidently.
- A stable `provider_job_id` is derived from the entry's permanent identifier,
  not from its position or title, so the same listing keeps its identity across
  fetches and consolidates correctly.
- Descriptions are HTML and pass through the shared sanitizer.
- Feeds are bounded. The adapter yields its entries as one or more bounded
  batches with an honest `total_pages` and warns when feed size limits truncate
  coverage.
- We Work Remotely's attribution and backlink requirement is preserved on every
  normalized result and in anything the frontend renders.

## Shared expectations

Both adapters follow the discipline the existing three established: a bounded
worker pool rather than one task per request, capped retry and backoff for 429,
timeout, and transient server responses honoring `Retry-After`, per-request
failures surfaced as warnings when results were already collected, description
sanitization through the shared sanitizer, no logging of payloads or response
bodies, and raw accepted objects retained internally for library snapshot
creation.

Both register through the JE-012 state resolution as key-less providers that are
always configured. Adding them increases fan-in volume, so the derived item
budget must account for the new enabled provider count exactly as JE-007
specifies. Neither adapter may introduce a parallel normalizer, sanitizer,
annualizer, or consolidation path.

## Out of scope

- Ranking behavior — JE-011
- Frontend presentation — JE-014
- Provider-quality weighting or preferring one provider's copy of a duplicate
  beyond the deterministic JE-008 rule
- Persisting provider catalogs, feed snapshots, or provider health
- Scraping HTML pages beyond the published feeds and APIs

## Acceptance criteria

1. Both adapters implement the unchanged `ProgressiveProvider` protocol and
   register as always-configured providers under JE-012 state resolution.
2. Remotive normalization — identity, title, company, job type, location text,
   timestamps, application URL, and attribution — passes contract tests against
   recorded responses.
3. Remotive free-text salary annualizes only when confident, leaves fields null
   otherwise, and never guesses a currency or a range from one figure.
4. We Work Remotely feed parsing passes contract tests against recorded feeds,
   including combined title-and-company separation, missing fields staying null,
   and a malformed entry being skipped without failing the feed.
5. We Work Remotely `provider_job_id` is stable across repeated fetches of the
   same listing and consolidates correctly under JE-008.
6. Both adapters warn when a documented cap or feed limit truncates coverage
   rather than reporting a truncated set as complete.
7. Attribution is preserved in every normalized result from both providers.
8. A failure in either provider yields `complete` with `is_partial` true and
   retained results from healthy providers; it never aborts another provider.
9. Duplicates spanning the new and existing providers consolidate under the
   existing JE-008 rules with every source preserved.
10. The derived item budget accounts for the increased enabled provider count,
    and a warm default index survives fan-in across all enabled providers.
11. No result from either provider is persisted, and JE-005, JE-007, JE-008,
    JE-011, and JE-012 behavior is otherwise unchanged.
