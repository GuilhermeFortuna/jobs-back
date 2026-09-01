# JE-011 — Relevance Ranking Engine Specification

## Status

Proposed for Batch 04. Depends on JE-010 for stored profile skills and the
shared normalizer, and on JE-005 and JE-007 for the progressive index and
fan-in semantics. Governed by
[ADR-002](../decisions/ADR-002-skill-based-relevance-and-provider-credentials.md).

## Purpose

Make `sort=relevance` mean something. Today it falls through to an alphabetical
`(provider, provider_job_id)` tiebreak, so the default ordering of every search
is arbitrary. This task scores results against the query and the profile's
skills, moves query and location filtering into the index so result membership
is consistent across providers, and reports why a job ranked where it did.

## Scoring model

The score is a pure function of one job, the query, and the profile's skill
tokens. It uses no corpus-wide statistics, so a job's score never changes as
other providers stream results in. This is required, not incidental: the index
serves partial results while loading, and scores that drifted with corpus
composition would reorder rows under the reader.

Contributions:

| Signal | Source | Behavior |
| --- | --- | --- |
| Query terms | Normalized query tokens against title, company, location text, description | Field-weighted, title strongest, description weakest |
| Query coverage | Fraction of distinct query tokens matched anywhere | Multiplies the query contribution; a job matching every term outranks one matching half of them twice |
| Skills | Profile skill tokens against the same fields | Field-weighted, additive, capped so a long skill list cannot dominate the query |
| Recency | `posted_at` | Bounded nudge only; never enough to lift an unrelated job above a matching one |

Rules the weights must satisfy, in preference to any specific numbers:

- A title match outranks a description match for the same term.
- A job matching more distinct query tokens outranks one matching fewer.
- Skill matches are additive and never subtractive. A job matching zero skills
  is ranked, not removed.
- The skill contribution is capped so that a profile with many skills does not
  reduce the query to noise.
- Recency cannot reorder jobs whose match strength differs.
- A job with an empty query and no skill matches still receives a defined score,
  in which case recency decides.

Weights are declared as named module constants with the rule each one serves,
not inlined as literals.

## Matching semantics

Both sides of a comparison are normalized by the shared module JE-010 landed:
case folded, punctuation and separators stripped, whitespace collapsed, so
`node.js` and `nodejs` reduce to one token. Matching is on word boundaries, not
substrings: `python` matches `Python 3` and not `pythonic`, and `go` does not
match `category`.

A curated alias table maps well-known equivalents in both directions —
`js`/`javascript`, `k8s`/`kubernetes`, `postgres`/`postgresql`, `react.js`/
`react`. It is declared as module-level data, deliberately small, and documented
as curated rather than exhaustive. It is a convenience for common abbreviations,
not a taxonomy, and it does not grow to encode job-market vocabulary.

## Determinism

Scoring is total, side-effect free, and independent of arrival order. Equal
scores fall back to the existing `_tiebreak` on `(provider, provider_job_id)`,
so two runs over the same result set produce identical pages. Consolidated
results are scored on the canonical source chosen by JE-008; alternate sources
do not add score.

## Match reporting

`JobResult` gains:

- `relevance_score`: the computed score, present for every returned item.
- `matched_skills`: the profile skill labels this job matched, in the profile's
  stored order, empty when none matched.

Reporting labels rather than tokens keeps the client free of normalization
rules. These fields are computed per search and are never persisted; a saved
snapshot records the job, not the ranking that surfaced it.

## Index-side filtering

`SearchFilters` gains `location`, a free-text field of at most 80 characters,
distinct from `country` and `worldwide`, which remain eligibility filters. It
matches the job's location text after normalization.

Query and location filtering are applied in the index after normalization,
alongside the existing salary and recency filters. Adapters may still push a
supported query or location upstream as a fetch-volume optimization, but result
membership is decided locally so it does not vary with which provider answered.

Membership rules:

- A non-empty query admits a job when every distinct query token matches at
  least one searchable field.
- A non-empty location admits a job when its normalized location text contains
  the normalized location value. A job with no location text is admitted only
  when the location filter is empty.
- Both filters participate in the canonical filter key, so they take part in
  warm-index reuse exactly as existing filters do.

## Out of scope

- Semantic search, embeddings, learned ranking, or any AI scoring
- Skills as an exclusion filter or a required-match rule
- Per-provider ranking bias or provider-quality weighting
- Persisting scores, rankings, or search results
- Frontend presentation of scores or matched skills — JE-014

## Acceptance criteria

1. `sort=relevance` orders by computed score with the existing stable tiebreak,
   and repeated runs over identical input produce identical pages.
2. Scoring is independent of provider arrival order, proven by delivering the
   same result set in several orders.
3. Each documented weight rule has a test asserting the ordering it guarantees,
   including title over description, higher token coverage, capped skill
   contribution, and bounded recency.
4. A job matching no skills is returned and ranked, never removed.
5. `matched_skills` reports the profile's stored labels for matched skills in
   stored order, and is empty when none match; `relevance_score` is present on
   every item.
6. Alias-table equivalents match: a profile skill of `k8s` matches a posting
   that says Kubernetes, and word-boundary matching prevents `python` matching
   `pythonic` and `go` matching `category`.
7. Query filtering happens in the index, so the same query yields the same
   membership regardless of which provider supplied a job.
8. `location` filters on normalized location text, is distinct from `country`
   and `worldwide`, and participates in the canonical filter key.
9. Ranking and index filtering leave progress, `checked_count`, `total`,
   partial-failure semantics, warm reuse, refresh, and eviction unchanged.
10. Scoring cost stays linear in item count under the existing 100,000-record
    benchmark.
11. No score, ranking, or search result is written to PostgreSQL.
