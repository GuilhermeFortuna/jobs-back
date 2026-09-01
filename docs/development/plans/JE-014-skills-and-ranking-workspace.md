# JE-014 — Skills and Ranking Workspace Implementation Plan

Implements
[`JE-014-skills-and-ranking-workspace.md`](../specs/JE-014-skills-and-ranking-workspace.md)
in `jobs-front`, last in Batch 04, against the finished JE-010, JE-011, and
JE-012 contracts.

## Implementation baseline — reuse, do not rebuild

| Existing work | Current evidence | Disposition |
| --- | --- | --- |
| `src/components/job-scout/profile-picker.tsx` | Profile selection and profile-scoped controls | Host the skills editor here; do not add a new page or route |
| `src/components/job-scout/filters-panel.tsx` | Query input with debounce, country select, provider filter, sort control | Add the location input alongside; follow the existing debounce and control patterns |
| `src/components/job-scout/job-card.tsx`, `job-detail.tsx` | Card and detail layout, provider attribution, multi-source badges | Add matched-skill chips; do not restructure layout |
| `src/hooks/use-job-scout.ts` | Search lifecycle, refresh polling, profile state | Extend for skills mutation and re-ranking; do not fork the hook |
| `src/lib/api.ts` | Typed API access layer | Extend types for `skills`, `matched_skills`, `location`, and provider `state` |
| `src/lib/search-params.ts` | URL filter serialization and restore | Extend with `location`; keep round-trip tests passing |
| `src/lib/providers.ts` | Provider option derivation from `GET /providers` | Extend for provider state; keep unconfigured providers unselectable |
| `src/components/ui/*` | shadcn primitives already in use | Compose from these; add no new UI dependency |

JE-006 and JE-009 suites pass today, including `search-params.test.ts`,
`filters-panel.test.tsx`, `job-card.test.tsx`, and `use-job-scout.test.tsx`.
Every existing assertion must keep passing.

## Remaining implementation

### Skills editor

1. Extend the API layer with the profile `skills` type and a patch call sending
   labels only.
2. Build the chip list and add/remove controls in the profile surface, composed
   from existing UI primitives, with keyboard-operable removal.
3. Mirror the server validation rules client-side with inline messages, and
   surface a 422 body as readable text rather than a generic failure.
4. Treat a patch as a wholesale list replacement, matching the backend contract,
   and refresh the search afterwards so the new ranking is what the user sees.
5. State at the point of editing that changes re-rank the next search.

### Ranking explainability

1. Extend the result types with `matched_skills` and `relevance_score`.
2. Render matched-skill chips on cards and in the detail view in API order,
   rendering nothing when the list is empty.
3. Do not render the score anywhere; add a test asserting it is absent from the
   DOM.
4. Add the relevance-sort explanation linking to the skills editor.

### Location filter

1. Add `location` to the filter type, the panel, and the URL serializer, keeping
   it distinct from the country select in both data and labelling.
2. Reuse the existing query debounce behavior rather than adding a second
   timing mechanism.
3. Extend the URL round-trip tests to cover location.

### Provider state

1. Extend provider option derivation with `state`, rendering `unconfigured`
   providers as unavailable and unselectable.
2. Assert no credential or configuration detail reaches the DOM.

## Test plan

- Skills editor tests: add, remove, persistence through patch, labels-only
  payload, reload restoration, empty-list state.
- Validation tests for the count cap, label length, duplicates, and a server 422
  rendering readable text.
- Matched-skill chip tests for populated and empty cases, and a test asserting
  no relevance score appears in the DOM.
- Location filter tests for filtering, URL round-trip, debounce, and
  independence from the country select.
- Provider state tests for an unconfigured provider rendering as unavailable,
  being unselectable, and leaking no configuration detail.
- Accessibility tests for keyboard operation of chips and the location input,
  and announced validation errors.
- Responsive QA at the project's supported breakpoints per the UI skill.
- Re-run of the JE-006 and JE-009 suites unchanged.

## Completion criteria

- Every JE-014 acceptance criterion has automated coverage.
- `./ci.sh` passes in `jobs-front`.
- Manual end-to-end verification against a running API via `./dev.sh`: edit
  skills, observe re-ranking under relevance sort, filter by location, and see
  an unconfigured provider presented as unavailable.
- No client-side ranking or filtering of returned results, no displayed score,
  and no backend contract change is introduced.
