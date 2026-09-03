# JE-019 — Application Shell and Theme Surface Implementation Plan

Implements
[`JE-019-application-shell-and-theme-surface.md`](../specs/JE-019-application-shell-and-theme-surface.md)
in `jobs-front`, after JE-018. Owns the shell files, so it lands before JE-020
and JE-021 to avoid three tasks editing the same layout.

## Implementation baseline — reuse, do not rebuild

| Existing work | Current evidence | Disposition |
| --- | --- | --- |
| `src/components/job-scout/header.tsx` | Header, dual navigation, mobile tab bar; imports zero `ui/*` primitives today | Rebuild on ledger components; keep the safe-area handling |
| `src/components/job-scout/index.tsx` | Three-pane shell, mobile sheets, page header, footer counter | Rebuild chrome only; leave the results list and detail content to JE-020 and JE-021 |
| `src/components/job-scout/profile-picker.tsx` | Picker plus four dialogs, whole JSX mounted twice | Render once; the skills dialog belongs to JE-021 |
| JE-016 theme mechanism | Provider and three-state control | Place and style it; do not reimplement the mechanism |
| `jobs-front/docs/design/component-source-ledger.md` | JE-015 output | Only permitted source for the navigation, chrome and ambient treatment |
| `jobs-front/docs/design/*.png` | JE-016 references | The visual target to match |
| Shared breakpoint constant | Extracted by JE-017 | Read it; do not reintroduce a literal |
| `src/hooks/use-job-scout.ts`, `src/lib/*` | State and pure logic | Untouched |

## Remaining implementation

1. Rebuild the header: logo mark, wordmark, and layout from ledger components.
2. Replace the two separate navigations with one responsive navigation built on a
   real primitive, exposing the active view. JE-017 made this assertable without
   requiring two navigation elements.
3. Render the profile picker once. Removing the duplicate mount also removes the
   duplicated select and dropdown from the tree — verify the e2e profile test,
   which currently uses `.first()` to cope with the duplication, still passes.
4. Place the JE-016 theme control in the header with a visible current state, an
   accessible label, and keyboard operation.
5. Rebuild the pane chrome for the filter rail, results column and detail pane on
   surface primitives and elevation tokens.
6. Rebuild the mobile bottom tab bar, preserving safe-area handling.
7. Add the ambient treatment to the header band from the ledger. Mark it
   `aria-hidden`, make it non-focusable and pointer-transparent, and confine it
   to the band.
8. Implement the reduced-motion static fallback and the mobile fallback. Measure
   before deciding whether the animated version ships on mobile.
9. Measure first paint against the pre-task baseline. If the ambient treatment
   regresses it, ship the static version and report the measurement.

## Test plan

- Navigation tests: active view exposed, keyboard operable, both breakpoints,
  passing with a single navigation element.
- A test asserting the profile picker renders once.
- Theme control tests: all three states reachable, current state discoverable,
  labelled, keyboard operable, at both breakpoints.
- Ambient treatment tests: absent from the accessibility tree, not focusable,
  not intercepting pointer events, and confined to the header band — asserted by
  checking it does not render within the results or detail regions.
- A reduced-motion test asserting the static fallback renders and the header
  remains legible.
- Sheet-versus-pane tests across the shared breakpoint constant, unchanged from
  JE-017's converted versions.
- Profile persistence tests: selection survives reload via `localStorage`, and
  the fallback notice still appears.
- First-paint measurement recorded against the baseline.
- Full re-run of the JE-006, JE-009 and JE-014 suites.
- Visual QA at 1440×1000 and 390×844 in both themes against the JE-016
  references.

## Completion criteria

- Every JE-019 acceptance criterion has automated coverage where automatable,
  with recorded measurements for first paint and the mobile ambient decision.
- `./ci.sh` passes in `jobs-front`; run `pnpm format` first.
- Manual end-to-end verification against a running API via `./dev.sh`: switch
  views, switch profiles, switch themes including system, and open the detail
  above and below the breakpoint — in both themes.
- `use-job-scout.ts`, `src/lib/`, and component prop types are unchanged.
- The filters panel, job card, job detail, search status and skills surfaces are
  not redesigned by this task. Chrome only.
