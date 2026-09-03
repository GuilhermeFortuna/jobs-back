# JE-021 — Detail, Library and Status Surfaces Specification

## Status

Proposed for Batch 05, implemented in `jobs-front`. Depends on JE-019. May run in
parallel with JE-020, which owns disjoint files. Last task in Batch 05.

## Purpose

Redesign the job detail, the search status region, and the profile and skills
surface. This is where the batch's remaining hand-rolled markup lives — a faked
tab bar, six duplicated banners, three dialogs built from the wrong primitive —
and where the search-in-progress moment earns an expressive treatment.

## Job detail

- Rebuilt on the primitives JE-018 installed. The fake tab bar — a bordered span
  imitating a single selected tab — is replaced by real tabs, with the content
  genuinely divided across them rather than a single pane behind a decoration.
- The company logo renders here as it does on the card, with the letter tile as
  the fallback. The card and detail currently maintain two divergent copies of
  the same letter-tile idea at different sizes; they become one component.
- The source list is rebuilt on the `card` primitive, keeping every source link,
  its accessible name, and the primary-source designation.
- The action bar keeps the three-way Save label logic exactly, and keeps the
  applied action on the JE-016 accent token rather than an inline color.
- Provider attribution, including the RemoteOK requirement, stays visible on
  every rendered result.
- Matched skills keep their JE-014 contract: API order, nothing rendered when
  empty, no relevance score anywhere.
- Saved snapshots remain viewable when the provider has removed the listing.

## Search status

The six near-duplicate banners — partial, warning, expired, offline, validation
and failed — are rebuilt on the `alert` primitive with JE-016 semantic tokens.
They collapse to one component with variants rather than six copies.

The search-in-progress state gets an expressive treatment. It is a moment a user
passes through while providers answer, and it currently renders as a text strip
with a progress bar. It carries real information — progress, roles checked,
per-provider status, partial results and warnings — and none of that may be lost
to decoration.

Constraints:

- The `aria-live` region and its announced strings are preserved. Strings stay
  generated in `src/lib/search-notice.ts`; this task changes where and how they
  render, not what they say.
- Exact totals continue to appear only when a search is complete.
- Per-provider status continues to distinguish loading, complete and failed, on
  semantic tokens rather than inline colors.
- Toasts introduced in JE-018 must not duplicate an inline message. Nothing is
  announced twice.
- The expressive treatment has reduced-motion and mobile fallbacks, and the
  status information remains fully legible when they apply.

## Profile and skills surface

- The three profile forms — create, rename, edit skills — move from
  `alert-dialog` to the `dialog` primitive JE-018 installed. The genuine
  confirmation for deleting a saved job stays an `alert-dialog`.
- The skills editor is rebuilt on the tag-input pattern from the ledger. Its
  JE-014 contract is preserved in full: chips in stored order, add by typing and
  confirming, remove from the chip, keyboard-operable removal, labels-only
  payload, wholesale list replacement, client guards mirroring the server rules
  for the fifty-skill cap and sixty-character limit and duplicates, a server 422
  surfaced as readable text, an empty list as a valid state, and the statement
  that editing re-ranks the next search.
- The three inline field errors are rebuilt on `field-error`.
- This is a pass-through surface, so an expressive treatment from the ledger is
  appropriate under the usual fallback rules.

## Library states

The saved and applied views keep their behavior. Their empty states are rebuilt
on the `empty` primitive alongside the ones JE-020 handles, coordinated so the
two tasks do not produce two different empty-state treatments.

## Behavior that must not change

- Component prop types, `use-job-scout.ts`, and every `src/lib/` module.
- Save, apply, and delete flows, including the delete confirmation.
- Unsaved detail resolution by `search_id` plus provider identity.
- Every accessible name and keyboard path the suite asserts.

## Out of scope

- Filters panel, results list and job card — JE-020.
- Shell, header, navigation and theme control — JE-019.
- Backend contract changes of any kind.

## Acceptance criteria

1. The job detail uses real tabs with content genuinely divided across them; no
   faked tab bar remains.
2. The card and detail share one logo/fallback component rather than two
   divergent copies.
3. The three-way Save label logic is unchanged, and the applied action uses the
   accent token with no inline color.
4. Provider attribution, including RemoteOK, remains visible; every source link
   keeps its accessible name and the primary source stays designated.
5. Saved snapshots remain viewable after a provider removes the listing.
6. The six banners are one component with variants, on semantic tokens.
7. The `aria-live` region and its strings are preserved, and strings remain
   generated in `src/lib/search-notice.ts`.
8. Exact totals appear only when a search is complete; per-provider status still
   distinguishes loading, complete and failed.
9. No message is announced twice across toasts and the inline region.
10. The search-in-progress treatment loses no information, and remains fully
    legible under reduced motion and at mobile breakpoints.
11. The three profile forms use `dialog`; the delete confirmation remains an
    `alert-dialog`.
12. Every JE-014 skills contract listed above is preserved, including
    keyboard-operable chip removal and readable 422 handling.
13. Matched skills render in API order, render nothing when empty, and no
    relevance score appears in the DOM.
14. Empty-state treatment is consistent with JE-020's.
15. Save, apply, delete and unsaved-detail resolution are unchanged.
16. Responsive and accessibility QA passes at both breakpoints in both themes
    against the JE-016 references.
