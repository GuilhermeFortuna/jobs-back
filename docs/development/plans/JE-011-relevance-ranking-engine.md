# JE-011 — Relevance Ranking Engine Implementation Plan

Implements
[`JE-011-relevance-ranking-engine.md`](../specs/JE-011-relevance-ranking-engine.md)
after JE-010 lands stored skills and the shared normalizer.

## Implementation baseline — reuse, do not rebuild

| Existing work | Current evidence | Disposition |
| --- | --- | --- |
| `search/relevance.py` | Normalizer and alias table from JE-010 | Extend the same module with scoring; add no second normalizer |
| `search/live.py` | `_filter`, `_sort`, `_tiebreak`, `canonical_filters`, `filter_key` | Extend query/location filtering and the relevance branch; do not restructure the lifecycle |
| `search/consolidation.py` | Canonical source selection, `alternate_sources` merge | Score the canonical source only; leave consolidation untouched |
| `schemas/discovery.py` | `JobResult`, `SearchFilters`, `SearchSort` | Add `relevance_score`, `matched_skills`, and `location`; keep `extra="forbid"` |
| `models/profile.py`, profile loading in `live.py` | Profile lookup already available to the manager for warming | Read stored skills through the existing path rather than adding a query per search |
| `tests/test_search_retention.py` | 100,000-record benchmark harness | Reuse to prove scoring stays linear |

JE-005, JE-007, JE-008, and JE-010 suites pass today. Every existing assertion on
progress, totals, reuse, refresh, and eviction must keep passing.

## Remaining implementation

### Scoring

1. Extend `search/relevance.py` with a `score_job` entry point taking the job,
   normalized query tokens, and profile skill tokens, returning a score and the
   matched skill tokens.
2. Declare every weight as a named module constant documenting the ordering rule
   it serves. No inline literals.
3. Implement field weighting over title, company, location text, and
   description, with the query coverage multiplier applied to the query
   contribution only.
4. Cap the skill contribution so a long skill list cannot swamp the query, and
   bound the recency component so it cannot reorder unequal match strengths.
5. Keep the function pure: no manager state, no corpus statistics, no clock read
   beyond a single `now` passed in, so tests are deterministic.

### Integration into the index

1. Resolve the profile's skill tokens once per search state, not once per item,
   and hold them on the state alongside the filters.
2. Score at the point items are ordered, and set `relevance_score` and
   `matched_skills` on returned results; map matched tokens back to stored
   labels in the profile's order.
3. Replace the relevance branch of `_sort` with score-descending plus the
   existing `_tiebreak`, leaving the `newest` and `salary` branches untouched.
4. Score the consolidated canonical item only; alternate sources contribute no
   score.

### Index-side filtering

1. Add `location` to `SearchFilters` and to `canonical_filters` so it takes part
   in the filter key.
2. Extend `_filter` with query-token membership and normalized location
   containment, alongside the existing salary and recency rules.
3. Audit each adapter's upstream query and location parameters, keeping them as
   fetch-volume optimizations, and confirm by test that local filtering decides
   membership regardless of upstream behavior.

## Test plan

- Scoring unit tests, one per documented weight rule, using fixed job fixtures
  and asserting the ordering the rule guarantees rather than exact scores.
- Order-independence tests delivering identical result sets in several provider
  arrival orders and asserting identical completed pages.
- Alias and word-boundary tests: `k8s` against Kubernetes text, `python` not
  matching `pythonic`, `go` not matching `category`.
- Match-reporting tests for `matched_skills` label text, ordering, and the empty
  case, and for `relevance_score` presence on every item.
- Membership tests proving the same query admits the same jobs across providers,
  including a provider whose upstream query support differs.
- Location filter tests covering match, no-location-text jobs, and independence
  from `country` and `worldwide`.
- Invariant tests asserting unchanged progress, `checked_count`, `total`,
  partial-failure behavior, reuse, refresh, and eviction.
- The 100,000-record benchmark rerun with a populated skill list to prove
  scoring stays linear.
- OpenAPI tests for the new result and filter fields.

## Completion criteria

- Every JE-011 acceptance criterion has deterministic automated coverage.
- `./ci.sh lint` and `./ci.sh test` pass against a real PostgreSQL database.
- Weights are named constants with documented rules, and the benchmark shows no
  superlinear cost.
- No semantic matching, no exclusionary skill behavior, no persisted ranking,
  and no frontend change is added.
