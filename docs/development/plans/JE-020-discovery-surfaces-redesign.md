# JE-020 — Discovery Surfaces Redesign Implementation Plan

Implements
[`JE-020-discovery-surfaces-redesign.md`](../specs/JE-020-discovery-surfaces-redesign.md)
in `jobs-front`, after JE-019. Runs in parallel with JE-021; the two own disjoint
files.

## Implementation baseline — reuse, do not rebuild

| Existing work | Current evidence | Disposition |
| --- | --- | --- |
| `src/components/job-scout/filters-panel.tsx` | Rendered twice from one component; five hand-rolled fields; two checkbox group implementations | Rebuild on JE-018 field primitives; keep the single-component, two-mount structure |
| `src/components/job-scout/job-card.tsx` | Hand-rolled article card, letter avatar, badge row, matched-skill chips, bookmark toggle | Rebuild on `card`; preserve every accessible name |
| Empty states, moved out of `job-card.tsx` by JE-018 | Offline, no-results, no-saved | Rebuild on the `empty` primitive |
| `src/lib/search-params.ts` | `filtersFromSearchParams`, `searchParamsFromFilters`, `mergeFilters`, `syncFiltersToUrl` | Reuse as-is. A control that changes type must still round-trip through these |
| `src/lib/job-utils.ts` | `money`, `age`, `sourceCount`, `countActiveFilters`, `preserveSelection` | Reuse for all display formatting; do not reimplement |
| `src/lib/api.ts` | `JobResult.company_logo_url`, search page contract | Read; do not change |
| `src/hooks/use-job-scout.ts` | `DEFAULT_FILTERS` imported by the panel; polls without `page` | Narrow exemption: page state, pass `{ page, page_size }` to `api.search`, reset page on new search. Nothing else |
| `next.config.ts` | Empty; no `images` key | The one Next config file this task must change |
| `jobs-front/docs/design/` | JE-015 ledger, JE-016 references | Only permitted component source; the visual target |

## Remaining implementation

### Filters panel

1. Rebuild the five fields on the field primitives, collapsing the four
   helper-text treatments into `field-description`.
2. Unify the two checkbox group implementations into one that carries the
   disabled/unavailable treatment as a state rather than a second copy.
3. Adopt the shared input-group for the keyword and location inputs.
4. If employment type or seniority moves to a toggle group, or salary to a
   slider, or groups become collapsible, verify URL round-trip through
   `search-params.ts` before and after. A control type change that alters the
   serialized value is a defect.
5. Preserve the shared debounce rather than introducing a second timing
   mechanism.

### Job card and results list

1. Rebuild the card on `card` with elevation tokens.
2. Add `images` configuration to `next.config.ts`. Prefer a per-provider
   allowlist; fall back to a wildcard only if impractical, and record the reason.
3. Render `company_logo_url`, falling back to the letter tile when the URL is
   absent or the image fails to load. Test the failure path explicitly — provider
   CDNs are unreliable and a broken image must not leave a blank tile.
4. Preserve matched-skill chips in API order, the empty-list absence, and the
   absence of any relevance score.
5. Preserve the save control's accessible name and keyboard operation, and the
   multi-source attribution treatment.
6. Add skeletons sized to the redesigned card so the list does not reflow.
7. Present the JE-018 pagination against the existing page contract. Wire it
   through the narrow `use-job-scout.ts` page-state exemption in the Spec —
   no client-side slicing of `items`.

### Empty states

1. Rebuild on the `empty` primitive.
2. Add an expressive treatment from the ledger, with reduced-motion and mobile
   fallbacks.

## Test plan

- URL round-trip tests for every filter, extended to cover any control that
  changed type, reusing the existing `search-params` test patterns.
- Debounce, active-filter count, reset, search, and save-as-default tests.
- Provider filter tests: unconfigured providers visible, unavailable,
  unselectable, no configuration detail in the DOM.
- Logo tests: renders when present, falls back to the letter tile when absent,
  and falls back when the image errors.
- Matched-skill chip tests for populated and empty cases, plus the standing
  assertion that no relevance score reaches the DOM.
- Skeleton tests asserting no layout shift when results replace the skeletons.
- Pagination tests against the existing page contract, with no client-side
  slicing: a page change issues `api.search` with the new `page`, and
  selection survives the page change.
- Progressive-update tests: selection preserved across updates, stale results
  visible during refresh.
- Reduced-motion test for the empty-state treatment.
- Full re-run of the JE-006, JE-009 and JE-014 suites and the JE-017 converted
  assertions.
- Visual QA at 1440×1000 and 390×844 in both themes against the JE-016
  references.

## Completion criteria

- Every JE-020 acceptance criterion has automated coverage where automatable.
- `./ci.sh` passes in `jobs-front`; run `pnpm format` first.
- Manual end-to-end verification against a running API via `./dev.sh`: run a
  search, adjust every filter, confirm the URL restores them, paginate, save a
  role, and observe logos loading from real providers — in both themes.
- Every `src/lib/` module is unchanged. `use-job-scout.ts` is the **sole**
  exemption and may only add page state, pass `{ page, page_size }` to
  `api.search`, and reset page on new search — recorded in the task report.
- `next.config.ts` is the only Next config change and its `images` choice is
  recorded in the report.
- No job detail, search status, or skills surface change ships with this task.
