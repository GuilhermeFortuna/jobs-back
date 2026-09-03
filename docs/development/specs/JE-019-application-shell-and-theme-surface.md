# JE-019 — Application Shell and Theme Surface Specification

## Status

Proposed for Batch 05, implemented in `jobs-front`. Depends on JE-018. First of
the three surface tasks; it owns the shell, so JE-020 and JE-021 follow it.

## Purpose

Redesign the frame the workspace lives in — header, navigation, profile picker,
three-pane chrome, mobile tab bar — and place the theme control and the ambient
expressive treatment. The information architecture does not change; how it looks
and feels does.

## Information architecture — fixed

Unchanged by this task and by Batch 05 generally:

- Desktop keeps three panes visible: filters, results list, job detail.
- Discover, Saved and Applied remain three first-class views.
- The profile picker remains in the header.
- Below the shared breakpoint constant JE-017 extracted, filters open in a sheet
  and the detail opens in a full-height sheet.
- Mobile keeps a bottom tab bar for view switching.

The breakpoint value itself may change, since JE-017 made it a single constant.
The sheet-versus-pane behavior may not.

## Shell redesign

- Header, wordmark and logo mark, rebuilt from ledger components rather than the
  current hand-rolled rotated tile.
- Navigation rebuilt with a real primitive. The current implementation is bare
  buttons with an `after:` pseudo-element underline, and renders as two separate
  navigations — desktop and mobile — with distinct accessible names. A single
  responsive navigation is permitted and preferred, which JE-017 made
  assertable.
- The profile picker is currently mounted twice, with the whole picker JSX
  rendered a second time inside a mobile dialog, so the select and dropdown exist
  twice in the tree simultaneously. The redesign renders it once.
- Pane chrome — the filter rail, the results column and the detail pane — rebuilt
  on the `card`/surface primitives with JE-016 elevation tokens.
- The mobile bottom tab bar rebuilt, keeping its current safe-area handling.

## Theme control

JE-016 delivered the mechanism; this task places and styles the control.

- Positioned in the header, reachable at both breakpoints.
- Exposes all three states: light, dark, system.
- Labelled for assistive technology and keyboard operable. It is an icon-level
  control, so the UI skill's labelling requirement applies.
- Its current state is discoverable without opening it.

## Ambient treatment

A restrained ambient treatment sits in the header band and fades into the
working surface. It is the batch's one always-visible expressive element, so it
is held to a stricter standard than the moment-based effects in JE-021:

- Sourced from the ledger, not hand-written.
- Confined to the header band. It does not render behind the results list or the
  job detail, which are read for long stretches.
- Legible in both themes, and designed for both rather than tinted from one.
- A static fallback under `prefers-reduced-motion`, and a static fallback at
  mobile breakpoints if the animated version costs meaningfully on a mid-range
  device.
- It must not trap pointer events, take focus, or appear in the accessibility
  tree.
- It must not regress first paint. If it cannot meet that, it ships static.

## Behavior that must not change

- View switching, profile selection and persistence through `localStorage`, and
  the profile fallback notice.
- The sheet-versus-pane detail behavior across the breakpoint.
- Every accessible name and keyboard path the suite asserts.
- Component prop types, `use-job-scout.ts`, and every `src/lib/` module.

## Out of scope

- Filters panel, results list and job card internals — JE-020.
- Job detail, search status, empty states and the skills surface — JE-021.
- Backend contract changes of any kind.

## Acceptance criteria

1. The three-pane desktop layout, the three views, the header profile picker,
   and the sheet-versus-pane behavior are all preserved.
2. Header, navigation, pane chrome and mobile tab bar are rebuilt from ledger
   components and JE-016 tokens, with no hardcoded color.
3. The profile picker is rendered once, not twice.
4. Navigation exposes the active view and is keyboard operable at both
   breakpoints.
5. The theme control is present in the header, exposes light, dark and system,
   shows its current state, and is labelled and keyboard operable.
6. The ambient treatment is confined to the header band and renders in neither
   the results list nor the job detail.
7. The ambient treatment has a static fallback under `prefers-reduced-motion`
   and remains legible when that rule applies.
8. The ambient treatment is not focusable, does not trap pointer events, and is
   absent from the accessibility tree.
9. First paint does not regress measurably against the pre-task baseline.
10. Profile selection, persistence, and the fallback notice are unchanged.
11. `use-job-scout.ts`, `src/lib/`, and component prop types are unchanged.
12. Responsive and accessibility QA passes at both breakpoints in both themes,
    matched against the JE-016 design references.
