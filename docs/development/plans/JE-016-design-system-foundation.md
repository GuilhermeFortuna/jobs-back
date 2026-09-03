# JE-016 — Design System Foundation Implementation Plan

Implements
[`JE-016-design-system-foundation.md`](../specs/JE-016-design-system-foundation.md)
in `jobs-front`, second in Batch 05, against the ledger delivered by JE-015.

## Implementation baseline — reuse, do not rebuild

| Existing work | Current evidence | Disposition |
| --- | --- | --- |
| `src/app/globals.css` | `@theme inline` alias block, `:root` with four brand overrides, an unreachable `.dark` block, a global reduced-motion rule | Extend into the full token system; keep the reduced-motion rule; delete the hardcoded `body` background |
| `src/app/layout.tsx` | Fraunces → `--font-display`, Geist → `--font-sans`, single `TooltipProvider` | Mount the theme provider here; resolve the unused Fraunces question |
| `src/components/ui/*` | 15 shadcn base-nova primitives | Retarget to tokens; do not restyle or replace |
| `src/components/job-scout/*` | 8 components holding 89 hex literals | Token substitution only — no layout, markup, or behavior change |
| `jobs-front/docs/design/component-source-ledger.md` | JE-015 output | Source for the theme toggle and any ambient treatment; do not source outside it |
| `jobs-front/docs/design/*.png` | Existing references | Replaced by this task's captures; delete the superseded files |
| `e2e/` and `src/**/*.test.tsx` | Existing suites, including the structure-coupled assertions JE-017 removes | Must keep passing unchanged. This task substitutes tokens without restructuring markup, so it does not depend on JE-017 and the two may run in parallel |

## Remaining implementation

### Token layer

1. Design the light and dark palettes together, treating dark as a first-class
   design rather than an inherited neutral set. Carry the brand identity into
   both.
2. Add semantic tokens for success, warning, info, destructive, and the
   applied-action accent, so the six alert families and the salary pill stop
   inlining color.
3. Add an elevation scale with per-theme values, replacing the two arbitrary
   `shadow-[…]` values.
4. Add a named type scale. Decide Fraunces' fate explicitly: wire
   `--font-display` into the scale, or remove the font from `layout.tsx`. Do not
   leave it loaded and unused.
5. Add motion duration and easing tokens.
6. Keep the `--radius`-derived scale; adjust the base value if the direction
   calls for it.

### Theme switching

1. Add the theme provider and mount it in `layout.tsx` alongside the existing
   `TooltipProvider`.
2. Deliver a three-state control — light, dark, system — defaulting to system.
   JE-019 places it; this task makes it work.
3. Prevent the first-paint flash with a blocking inline script or the library's
   equivalent.
4. Remove the hardcoded `body` background from `globals.css`.
5. Verify that a system preference change while the app is open is reflected
   without a reload.
6. Check AA contrast in both themes for text and interactive controls, and
   record the result.

### Hex literal elimination

1. Work file by file through the eight `job-scout/` components, substituting
   tokens for literals. Change nothing but color, shadow, and focus treatment.
2. Replace the eight-times-repeated focus ring string with one token-driven
   treatment.
3. Retarget the Progress primitive to a token and delete the
   `[&_[data-slot=progress-indicator]]` selector.
4. Finish with a grep proving no literal survives outside `globals.css`.

### Design reference

1. Capture desktop 1440×1000 and mobile 390×844 in both themes with Playwright,
   reusing the existing e2e viewport definitions rather than inventing new ones.
2. Write the short direction statement covering surfaces, where animation is and
   is not used, and the fallbacks.
3. Delete the superseded reference PNGs in the same change.

## Test plan

- A grep test asserting no hex literal exists under `src/` outside
  `globals.css`.
- Theme tests: default resolves to system; explicit light and dark selections
  apply and persist across reload; a system preference change while mounted is
  reflected.
- A first-paint test asserting no incorrect-theme flash.
- Contrast verification for text and interactive controls in both themes,
  recorded in the task report.
- A reduced-motion test asserting every animated treatment remains legible and
  its static fallback renders when the rule applies.
- Visual QA at 1440×1000 and 390×844 in both themes per the UI skill, compared
  against the new references.
- Full re-run of the JE-006, JE-009, and JE-014 suites unchanged. Token
  substitution must not alter behavior, so any diff in those suites is a defect
  in this task.

## Completion criteria

- Every JE-016 acceptance criterion has automated coverage where automatable, and
  recorded manual evidence where not — contrast and visual comparison in
  particular.
- `./ci.sh` passes in `jobs-front`. Run `pnpm format` first; this task touches
  many files and `prettier --check .` will otherwise fail CI on formatting alone.
- Manual end-to-end verification against a running API via `./dev.sh` in both
  themes: run a search, filter, save, apply, and edit skills.
- New design references are committed for both themes at both breakpoints and the
  superseded ones are deleted.
- No layout, markup structure, or behavior change ships with this task. A diff
  that moves an element is out of scope and belongs to JE-019 through JE-021.
