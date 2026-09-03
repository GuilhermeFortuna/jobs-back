# JE-014 — Skills and Ranking Workspace Specification

## Status

Proposed for Batch 04, implemented in `jobs-front`. Depends on JE-010 for the
profile skills contract, JE-011 for ranking fields and the location filter, and
JE-012 for provider state. Governed by
[ADR-002](../decisions/ADR-002-skill-based-relevance-and-provider-credentials.md).

## Purpose

Give the workspace the surfaces Batch 04's backend work requires: a place to
edit skills, a reason for the relevance ordering, a location filter, and an
honest presentation of providers that cannot answer.

## Skills editor

Skills are profile-level durable intent, so they are edited where the profile
is managed rather than inside the search filter panel. Mixing them into the
filters would suggest they narrow results, which they never do.

- Skills render as a list of chips in the profile surface, in stored order.
- A skill is added by typing a label and confirming; it is removed from its
  chip. Both actions persist through the profile patch contract, which replaces
  the list wholesale.
- The client sends labels only and never derives or sends a token.
- Client-side guards mirror the server rules — the 50-skill cap, the 60
  character label limit, and duplicate rejection — and show the reason inline.
  The server remains authoritative; a 422 is surfaced as a readable message
  rather than a silent failure.
- Editing skills re-ranks the next search. The workspace states this plainly at
  the point of editing so a reordered result set is not surprising.
- An empty skill list is a valid state and is presented as an opportunity, not
  an error.

## Ranking explainability

- Matched skills appear on a job card as compact chips, sourced from
  `matched_skills`, in the order the API returns them.
- A card with no matched skills shows no chips and no empty container. Absence
  of a match is not a negative signal and must not be rendered as one.
- The job detail view lists matched skills alongside the existing fields.
- `relevance_score` is not displayed as a number. A raw score invites
  comparison across searches, where it has no meaning. Its effect is visible
  through ordering and through matched-skill chips.
- Under `sort=relevance` the workspace states that ordering reflects the
  profile's skills, linking to the skills editor.

## Location filter

- The filters panel gains a free-text location input, distinct from the existing
  country select, labelled so the difference between where a role is and where a
  profile may work is clear.
- It participates in the existing URL filter serialization and restore path, so
  a shared or reloaded URL reproduces the same search.
- It is debounced consistently with the existing query input rather than
  triggering a search per keystroke.

## Provider state

- Providers reported as `unconfigured` by `GET /providers` are shown as
  unavailable rather than omitted, so their absence from results is explained
  rather than mysterious.
- An unconfigured provider cannot be selected as a filter.
- No credential detail, key name, or configuration hint is rendered.
- Existing per-provider status, multi-source attribution, and partial-result
  reporting from JE-009 are unchanged.

## Presentation constraints

Existing Job Scout UI conventions apply unchanged: the responsive layout, the
component structure under `components/job-scout/`, the API access layer in
`lib/api.ts`, and the accessibility and responsive QA rules in the project's UI
skill. Attribution requirements from every provider, including the adapters
added in JE-012 and JE-013, remain visible on rendered results.

New interactive controls are keyboard operable, labelled for assistive
technology, and announce validation errors. Skill chips are removable by
keyboard, not by pointer alone.

## Out of scope

- Skill suggestions, autocomplete, or inferred skills
- Any client-side scoring, re-ranking, or filtering of returned results
- Skills as a filter or exclusion control
- Displaying raw relevance scores
- Backend contract changes of any kind

## Acceptance criteria

1. Skills can be added and removed through the profile surface, persist through
   the profile patch contract with stored order intact, and survive reload.
2. The client sends labels only; no token is derived or sent.
3. Client guards for the count cap, label length, and duplicates show inline
   reasons, and a server 422 surfaces as a readable message.
4. An empty skill list renders as a valid, non-error state.
5. Matched skills render as chips on cards and in the detail view, in API order,
   with nothing rendered when there are no matches.
6. No raw relevance score is displayed anywhere.
7. Under relevance sort the workspace explains that ordering reflects profile
   skills and links to the editor.
8. The location input filters searches, is distinct from the country select,
   round-trips through URL serialization and restore, and is debounced like the
   query input.
9. Unconfigured providers are shown as unavailable, cannot be selected, and
   expose no credential or configuration detail.
10. Provider attribution stays visible for every provider, including the new
    adapters.
11. New controls are keyboard operable and accessible, and responsive QA passes
    at the project's supported breakpoints.
12. JE-006 and JE-009 behavior — refresh polling, URL filter restore, per-
    provider status, multi-source attribution, saved and applied flows — is
    unchanged.
