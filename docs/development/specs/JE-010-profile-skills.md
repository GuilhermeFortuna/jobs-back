# JE-010 — Profile Skills Specification

## Status

Proposed for Batch 04. Depends on JE-004 for the profile model, isolation rules,
and API surface. Governed by
[ADR-002](../decisions/ADR-002-skill-based-relevance-and-provider-credentials.md),
which admits skills as a persisted category of durable user intent under the
ADR-001 persistence constraints.

## Purpose

Let a profile record the skills it cares about so relevance ranking has a
durable signal beyond the ad-hoc query. This task delivers the data, the
contract, and the cache consequence only. Scoring itself is JE-011.

## Data model

Skills belong to the profile, not to its default search preferences. They are
not a filter, they do not appear in `SearchFilters`, and they take no part in
the canonical filter key.

Migration `006` adds one column to `profiles`:

| Column | Type | Rules |
| --- | --- | --- |
| `skills` | `JSONB`, not null, server default `'[]'` | JSON array of skill objects, ordered as the user entered them |

Each element has exactly two fields:

```json
{"label": "Node.js", "token": "nodejs"}
```

`label` is the display form the user typed, preserved verbatim after trimming.
`token` is the normalized matching form derived from the label by the shared
normalizer, stored so that ranking never re-derives it per search and so that
the runtime and any future backfill cannot drift.

Constraints:

- At most 50 skills per profile.
- `label` is 1 to 60 characters after trimming surrounding whitespace.
- A label that normalizes to an empty token is rejected.
- Tokens are unique within a profile. Two labels that normalize to the same
  token are a duplicate and the write is rejected; the collision is never folded
  silently. The rejection names both labels and the token they share, because a
  collision is often caused by the alias table rather than by an obvious repeat
  — `k8s` and `kubernetes` are duplicates and do not look like it.
- Order is preserved as given; it is presentation order and carries no ranking
  weight.

The normalizer that derives `token` is shared with ranking. JE-010 lands it, and
JE-011 extends the same module with scoring. Its matching semantics — word
boundaries, punctuation handling, and the alias table — are specified by JE-011.
Neither task may define a second copy.

## API contract

Skills ride the existing `/profiles` routes. No new endpoint.

- `ProfileRead` gains `skills: list[Skill]`.
- `ProfileCreate` accepts an optional `skills` list, defaulting to empty.
- `ProfilePatch` accepts an optional `skills` list. A present list replaces the
  stored list wholesale; an absent field leaves it unchanged. There is no
  partial add or remove operation.
- Clients send labels only. The server derives every `token`. A client-supplied
  token is rejected by `extra="forbid"` on the request model.

Validation failures return 422 with a message naming the offending rule. All
reads and writes remain scoped by `profile_id`; a profile can never observe or
modify another profile's skills.

## Cache invalidation

Live search states are keyed on `(profile_id, filters)` by `filter_key`.
Relevance depends on skills, which are outside that key, so a skills change
would otherwise be served a warm index ranked against the previous list.

A write that changes a profile's stored skills discards that profile's cached
search states. The next search for that profile runs fresh and ranks against the
current list. A write that leaves skills byte-identical discards nothing.

Discarding is scoped to the owning profile. It must not disturb another
profile's warm indexes, must not interrupt a refresh another profile is being
served from, and must leave the eviction pass, TTL handling, and shutdown
behavior specified by JE-005 unchanged.

## Out of scope

- Scoring, matching, or the alias table — JE-011
- Skill suggestions, autocomplete, taxonomies, or inferring skills from a resume
- Skills as a filter or an exclusion rule
- Frontend editing — JE-014
- Any change to `SearchFilters`, the canonical filter key, or provider adapters

## Acceptance criteria

1. Migration `006` adds the `skills` column with its default, and its downgrade
   drops the column cleanly; both are proven against a real PostgreSQL database.
2. A profile round-trips skills through create, read, patch, and list with order
   and labels preserved exactly.
3. Every documented validation rule — count cap, label length, empty token,
   duplicate token — returns 422 and does not write.
4. Server-derived tokens match the shared normalizer for a table of labels
   including punctuation, casing, and dotted forms; a client-supplied token is
   rejected.
5. Patching skills discards only the owning profile's cached search states, and
   a subsequent search reflects the new list.
6. Patching a profile without a `skills` field leaves stored skills unchanged
   and discards nothing.
7. Profile isolation holds: no read or write path exposes another profile's
   skills.
8. JE-004, JE-005, JE-007, and JE-008 suites pass unchanged, including warm
   index reuse, refresh, and eviction behavior.
