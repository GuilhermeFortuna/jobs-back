# JE-006 — Personal Job Discovery Frontend Implementation Plan

Implements
[`JE-006-personal-job-discovery-frontend.md`](../specs/JE-006-personal-job-discovery-frontend.md)
against JE-004 and JE-005.

## Implementation baseline — reuse, do not rebuild

This frontend work is in the sibling `jobs-front` repository.

| Existing work | Current evidence | Disposition |
| --- | --- | --- |
| shadcn initialization and UI primitives | `components.json`, Base UI/shadcn components, dependencies and lockfile | Retain; remove unused generated primitives only during normal cleanup |
| `src/components/job-scout.tsx` | Three-pane desktop, mobile filters/detail sheets, cards, detail, profile picker, library navigation | Refactor into maintainable components; do not restart the page |
| `src/lib/api.ts` | Typed calls for profiles, search polling, library state, and deletion | Retain but update to final JE-004/005 contracts |
| `globals.css`, layout, page | Visual tokens, reduced motion, metadata, app entry | Retain and review accessibility |
| Design artifacts | Concept and implementation screenshots in `docs/design` | Use for fidelity QA |
| Cursor skills | shadcn/Vercel skills plus `.cursor/skills/job-scout-ui` | Retain; use them during review |

Current verification: ESLint, TypeScript, and `next build` pass. Playwright at
1440×1000 and 390×844 showed the primary surfaces; tapping a mobile job opened
the detail sheet. A clean browser load with the backend running had no new
console errors. No frontend automated tests exist.

## Remaining implementation

### Structure and data flow

1. Split the large workspace into focused profile, filter, result-list, card,
   detail, library, and status components while preserving the verified layout.
2. Centralize query/loading/error state in one hook or store with cancellation
   on profile/filter changes. Prevent stale polling loops from replacing newer
   results.
3. Read supported filters from the URL during initialization and keep all
   meaningful filters/sort synchronized without destroying unrelated history.
4. Use the profile default only when the URL does not override it. Make “save as
   default” explicit and confirm success.
5. Replace the module-scoped profile boot workaround with a tested initialization
   path that behaves correctly under React Strict Mode.

### Profile and library workflows

1. Add profile create and rename UI and a predictable missing/removed-profile
   fallback. Continue remembering only the selected profile ID locally.
2. Update save requests to send `search_id` plus provider identity, allowing the
   backend to write an authoritative snapshot.
3. Represent saved/applied state consistently in discover cards and detail.
   Treat idempotent save as success.
4. Implement applied → saved and saved → applied from library views.
5. Add an accessible confirmation dialog before permanent deletion and preserve
   list/detail selection after mutation.

### Progressive and responsive behavior

1. Keep partial and stale results visible during loading/refresh. Display exact
   totals only when the backend says complete.
2. Add distinct provider warning, expired-search recovery, offline/retry, empty,
   and validation states. Development preview data must never appear as live
   results in a production build.
3. Ensure mobile content is not hidden by fixed navigation, sheets restore focus,
   and all desktop panes scroll independently without page overflow.
4. Preserve selected job during progressive updates; resolve unsaved detail by
   search/provider identity and saved detail by durable snapshot ID.
5. Review every icon control, tab, card, checkbox, select, dialog, and external
   link for accessible name, keyboard use, focus visibility, and reduced motion.

### Source-first component pass

For each remaining UI need, document the searched source and selected component.
Use existing shadcn primitives first. Add React Bits/Magic UI/21st components
only when they materially improve behavior; do not add decorative dependencies
for their own sake. Keep the existing job-specific layout composition.

## Test and QA plan

- Add component tests for URL initialization, profile memory, progress/total
  semantics, stale polling cancellation, empty/error states, and mutation state.
- Add Playwright journeys for first profile, live search, select detail, save,
  mark applied, move back to saved, profile isolation, and confirmed deletion.
- Mock JE-004/005 deterministically in CI; keep one separately invoked local
  backend journey.
- Capture 1440×1000 and 390×844 screenshots after final data-contract changes.
  Compare navigation, pane hierarchy, selected card, progress, actions, mobile
  filter sheet, and detail sheet with the references.
- Run ESLint, formatting check, production build, component tests, Playwright,
  and an accessibility scan.

## Completion criteria

- Every JE-006 acceptance criterion is demonstrated by automated or explicitly
  recorded manual QA.
- The final JE-004/005 contract is used; no client-supplied raw snapshot remains.
- The interface contains no unlabeled preview/fabricated provider data.
- Desktop/mobile screenshots and the end-to-end personal workflow are approved.

