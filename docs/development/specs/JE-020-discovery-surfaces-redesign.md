# JE-020 — Discovery Surfaces Redesign Specification

## Status

Proposed for Batch 05, implemented in `jobs-front`. Depends on JE-019. May run in
parallel with JE-021, which owns disjoint files.

## Purpose

Redesign the two surfaces a user works in continuously — the filters panel and
the results list — against the JE-016 references. These are read for long
stretches, so the standard is density, legibility and calm, not spectacle.

## Filters panel

The panel is rendered twice, as a desktop rail and inside a mobile sheet, from
one component. That stays.

- Rebuilt on the field primitives JE-018 installed, replacing the five
  hand-rolled `label`/`span` copies and the four helper-text treatments.
- The two checkbox group implementations — one for filter groups, one for
  providers with a disabled treatment — are unified into one.
- Employment type and seniority may move to a toggle group where that reads
  better than checkboxes, provided the filter semantics are identical.
- Minimum salary may move from a four-option select to a slider, provided the
  resulting values still round-trip through URL serialization unchanged.
- Filter groups may become collapsible via the accordion primitive.
- The keyword and location inputs use the shared input-group pattern rather than
  the duplicated hand-rolled version.

Behavior that must not change: URL addressability and restore for every filter,
the debounce shared by the keyword and location inputs, the distinction between
role location and eligibility country, the active-filter count, reset, "search
these roles", and "save as default".

Providers reported unconfigured remain visible, unavailable and unselectable,
with no credential or configuration detail rendered.

## Results list and job card

- The job card is rebuilt on the `card` primitive with JE-016 elevation tokens,
  replacing the hand-rolled article with its two inline shadow values.
- **Company logos ship.** `company_logo_url` is present on every result and is
  rendered today by nothing; both card and detail fall back to a letter tile.
  This task renders the real logo with the letter tile as the fallback for a
  missing or failed image. Provider logo URLs are arbitrary remote hosts, so
  `next.config.ts` needs an `images` configuration — currently the file is empty.
  A permissive wildcard is acceptable only if a per-provider allowlist is
  impractical, and the choice is recorded.
- Matched-skill chips keep their JE-014 contract: rendered in API order, nothing
  rendered when the list is empty, and no relevance score displayed anywhere.
- The save/bookmark control keeps its accessible name and keyboard operation.
- Multi-source attribution and the provider-count treatment are preserved.
- Skeletons replace the bare loading string, sized to the redesigned card so the
  list does not reflow when results arrive.
- Pagination, installed in JE-018, is presented here. The design reference shows
  it; the current list is unbounded.

## Empty and error states

The results-side empty states — offline, no results, and no saved roles — are
rebuilt on the `empty` primitive that JE-018 moved out of the job card file.
These are pass-through screens rather than working surfaces, so an expressive
treatment from the ledger is appropriate, subject to the same reduced-motion and
mobile fallback rules as every other effect in the batch.

## Behavior that must not change

- Component prop types, `use-job-scout.ts`, and every `src/lib/` module,
  including `job-utils.ts` formatting helpers and `search-params.ts`
  serialization.
- Progressive result updates and selection preservation across them.
- Stale results remaining visible during a refresh.

## Out of scope

- Job detail, search status, profile and skills surfaces — JE-021.
- Shell, header, navigation and theme control — JE-019.
- Backend contract changes. If pagination or logos require one, report it.

## Acceptance criteria

1. The filters panel is rebuilt on field primitives, with one unified checkbox
   group implementation and no duplicated search-input markup.
2. Every filter round-trips through URL serialization and restore unchanged,
   including any control that changed type.
3. The keyword and location debounce, the role-location versus eligibility
   distinction, the active-filter count, reset, search and save-as-default all
   behave as before.
4. Unconfigured providers remain visible, unavailable and unselectable, leaking
   no configuration detail.
5. The job card is rebuilt on the `card` primitive with elevation tokens and no
   hardcoded color.
6. Company logos render from `company_logo_url`, with the letter tile as the
   fallback for a missing or failed image, and `next.config.ts` is configured
   accordingly with the choice recorded.
7. Matched-skill chips render in API order, render nothing when empty, and no
   relevance score appears in the DOM.
8. The save control keeps its accessible name and keyboard operation;
   multi-source attribution is preserved.
9. Skeletons replace the loading string and are sized so the list does not
   reflow when results arrive.
10. Pagination is presented and works against the existing search page contract.
11. Empty states are rebuilt on the `empty` primitive, with reduced-motion and
    mobile fallbacks for any expressive treatment.
12. Progressive updates, selection preservation and stale-result behavior are
    unchanged.
13. Responsive and accessibility QA passes at both breakpoints in both themes
    against the JE-016 references.
