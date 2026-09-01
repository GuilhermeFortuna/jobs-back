# ADR-002 — Skill-Based Deterministic Relevance and Credentialed Providers

## Status

Accepted for Batch 04 on 2026-09-01. Extends
[ADR-001](ADR-001-personal-library-live-search.md) without superseding it. Every
ADR-001 constraint on persistence, live search, and profile isolation remains in
force.

## Context

Three facts about the system as Batch 03 leaves it drive this decision.

`relevance` is the default sort and is not implemented. `_sort` in
`search/live.py` falls through to a `(provider, provider_job_id)` alphabetical
tiebreak, so the default ordering of every search is effectively arbitrary. The
V1 goal lists sort by relevance as a minimum capability.

Keyword narrowing happens inside provider adapters, not in the index. Each
provider interprets a query differently, so the fan-in delivered by JE-007
produces a result set whose membership depends on which board answered rather
than on what the profile asked for. The goal's filter list also names location,
which no filter currently expresses; `country` and `worldwide` cover
eligibility, not place.

Provider coverage is three remote-only boards with heavy overlap. The goal's
provider strategy asks for maximum useful non-overlapping coverage, and the
strongest remaining candidates include at least one — Adzuna — that requires
credentials. Every adapter to date runs key-less, so the registry has no concept
of a provider that is enabled but cannot function.

Adding providers before ranking works would make the workspace worse: more
results, still ordered alphabetically.

## Decision

1. **Skills are durable user intent and are persisted.** A profile owns an
   ordered list of skills. ADR-001 restricts PostgreSQL to profile identity,
   default preferences, and saved or applied snapshots; skills join that
   enumeration as a fourth persisted category of intent. They are stored on the
   profile, not inside the `preferences` blob, because they are not a search
   filter and do not participate in the canonical filter key.

2. **Skills rank; they never exclude.** A job that passes the active filters is
   returned whether or not it matches a skill. Skill hits raise a job's score
   under `sort=relevance` only. Provider description quality varies enough
   across boards that an exclusionary skill filter would hide real roles for
   reasons that have nothing to do with the role.

3. **Relevance is deterministic and explainable.** Scoring is a pure function of
   the job, the query, and the profile's skills: field-weighted term and skill
   matching with a bounded recency component. No corpus-wide statistics, so a
   job's score does not change as other providers stream in — required by the
   progressive index, where results are rendered before the search completes.
   Ranking carries the matched skills back to the client so an ordering can be
   explained rather than trusted.

4. **Skill matching is token-based with a maintained alias table.** Both sides
   are normalized — case folded, punctuation stripped, `node.js` and `nodejs`
   collapsing to one token — and matched on word boundaries, so `python` matches
   `Python 3` and not `pythonic`. A small curated alias table maps well-known
   equivalents (`js`/`javascript`, `k8s`/`kubernetes`, `postgres`/`postgresql`).
   Substring matching is rejected: short skill names like `go` and `r` would
   match unrelated prose and poison the ranking.

5. **Query and location filtering move into the index.** Adapters may still push
   supported filters upstream as an efficiency, but membership of the result set
   is decided after normalization, so it is consistent across providers.

6. **Configured is distinct from enabled.** A provider declares the credentials
   it requires. A provider that is enabled but missing them is reported as
   unconfigured: it does not participate in fan-in, does not count against the
   fan-in memory budget, and is not offered to clients as a filter option.
   Startup does not fail — a missing optional key must not take the application
   down.

7. **Ranking ships before coverage.** JE-010 and JE-011 land before the new
   adapters in JE-012 and JE-013.

## Consequences

Cached search states are keyed on `(profile_id, filters)`. Relevance now also
depends on the profile's skills, which are outside that key, so editing skills
would serve stale ordering from a warm index. Writing skills therefore
invalidates that profile's cached search states. Widening the key with a skills
fingerprint was rejected: it would fragment the warm-index reuse that JE-005
exists to provide.

The alias table is a maintenance surface the project now owns. It is kept small,
declared as data rather than code, and documented in the JE-011 spec. It is not
allowed to grow into a taxonomy.

Deterministic scoring is weaker than semantic matching at understanding intent.
That is accepted: semantic search, AI ranking, and resume matching are out of
scope for V1, and this decision does not open them.

Adzuna's free tier is quota-limited. A provider exhausting its quota degrades to
a partial result under the existing JE-007 partial-failure semantics rather than
failing the search.

`JobResult` gains ranking fields, and results are still not persisted. Nothing
here revives catalog persistence, adds authentication, or introduces a second
backend process.
