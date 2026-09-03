# JE-022 — Ink and Acid Visual Identity Specification

## Status

Proposed for Batch 05, implemented in `jobs-front`. Depends on JE-021. Runs last
in the batch: it re-skins surfaces JE-019 through JE-021 have already finished,
so it must not start before they land.

## Purpose

Replace the JE-016 color palette and type pairing with a dark-first identity.
JE-016 authored light and derived dark from it, producing blue-tinted navy
surfaces with an indigo primary and a coral applied accent — a palette that reads
as generic and leaves dark mode a dimmed light mode rather than a designed one.
This task authors **dark first** and derives light from it.

The information architecture, component composition, and every backend contract
are unchanged. This task changes token values, the loaded typefaces, and the
three markup details the new palette forces.

## Identity — fixed by this spec

**Surfaces are ink.** True neutral near-black with no hue tint, sourced from the
Radix Colors dark `gray` scale. The absence of a blue tint is the point; a
re-tinted navy is a failure of this task.

**One accent: acid citron `#c6f24a`.** Emphasis is expressed by *weight*, not by
a second hue:

| Weight | Use |
| --- | --- |
| Solid citron fill, near-black text | Primary action (search, confirm, submit) |
| Outlined citron, citron text | Applied state |
| Neutral raised surface | Secondary action (save, cancel) |

A second saturated brand accent is out of scope. `--applied` becomes citron and
is expressed as an outline, not a fill; coral is removed from both themes.

**Semantic colors stay semantic.** Amber warning, red destructive and green
success remain, reserved for state. Because success-green neighbors citron on the
wheel, success is confined to confirmations — it may no longer carry salary.

## Typography — fixed by this spec

| Role | Face | Source | Licence |
| --- | --- | --- | --- |
| UI (`--font-sans`) | General Sans | Fontshare | ITF Free Font Licence |
| Display (`--font-display`) | Cabinet Grotesk | Fontshare | ITF Free Font Licence |

Geist and Fraunces are removed. Neither replacement is on Google Fonts, so
`layout.tsx` moves from `next/font/google` to `next/font/local` with the `woff2`
files committed under `src/app/fonts/`. Self-hosting is required, not optional:
it keeps the licence terms satisfied, removes a third-party request, and
preserves the existing no-FOUT behavior.

`--font-heading` continues to alias `--font-display`.

## Markup changes the palette forces

These three are in scope. Nothing else in the components changes.

1. **Salary chips go neutral.** Today the salary chip is success-green. Green
   beside citron makes the accent ambiguous. Salary renders on a neutral "data"
   token pair (`--data-foreground` / `--data-border`), not on success.
2. **Applied rows get a position cue.** Tiered citron expresses applied as an
   outline, which is quieter than the coral fill it replaces. Applied cards carry
   a 3px citron left rule and a citron "Applied" tag, so the state survives at
   list density. The state is not conveyed by color alone.
3. **The applied badge inconsistency is corrected.** `job-card.tsx` currently
   renders the applied badge as `bg-applied-soft text-destructive` — applied
   background with destructive text. It moves onto the applied token pair.

## Ambient treatment

`header-ambient.tsx` reads `--primary` through `useThemePrimaryColor`, so the
hue follows the token with no code change. The **opacity does not**: acid citron
at `maxOpacity={0.18}` on near-black is far louder than indigo on navy. Both the
animated and the static fallback opacities are retuned so the band stays ambient.
The JE-019 contract is otherwise preserved: animated on `sm+` when motion is
allowed, static radial-grid fallback on mobile and under
`prefers-reduced-motion`.

## Light theme — derived

Light is derived from the dark identity, not authored independently. Paper
neutrals (warm-neutral, not blue), the same citron primary fill with near-black
text, and the same tiered weights.

One derived-mode constraint: **citron as text fails AA on light backgrounds.**
Light mode therefore defines a separate `--primary-emphasis` for citron-as-text
(a deeper olive-citron), while citron-as-fill keeps `#c6f24a` with near-black
text. Dark mode has no such split.

## Out of scope

- Information architecture, pane layout, breakpoints, sheet-versus-pane behavior
- Any backend contract
- `src/hooks/use-job-scout.ts` and every module under `src/lib/` (Batch 05 rule 6)
- Installing any component not on the JE-015 ledger (Batch 05 rule 5). This task
  installs no components; it changes token values, fonts, and three markup
  details.
- A second brand accent, and any new expressive or animated treatment

## Acceptance criteria

1. `.dark` token values define ink neutrals with no hue tint, and `--primary` is
   `#c6f24a` in both themes.
2. `--applied` is citron in both themes; no coral value (`#f26450`, `#f28474`)
   remains in `globals.css`.
3. The applied state renders as a citron outline plus a 3px left rule and an
   "Applied" tag — never as a solid citron fill, which is reserved for primary
   actions.
4. Salary renders on the neutral data token pair. `--success` is not used for
   salary anywhere.
5. The applied badge uses applied-token foreground, not `text-destructive`.
6. `layout.tsx` loads General Sans and Cabinet Grotesk through `next/font/local`
   from `woff2` files in the repo. No `next/font/google` import remains, and no
   runtime request reaches a font CDN.
7. Ambient opacity is retuned; the header band reads as ambient rather than as a
   citron field, and the JE-019 animated/static/reduced-motion contract is intact.
8. No hardcoded color is introduced in any component. Every color resolves through
   a semantic token — the same rule JE-020 and JE-021 were held to.
9. `docs/design/visual-direction.md` is rewritten for this identity, including a
   regenerated WCAG AA contrast table covering foreground, primary fill, muted
   text, applied outline, and the light-mode `--primary-emphasis` split.
10. The four reference screenshots (`job-scout-{desktop,mobile}-{light,dark}.png`)
    are recaptured at 1440×1000 and 390×844.
11. The JE-017 behavioral test contracts pass unchanged. A test that fails because
    it asserted a JE-016 color is a defect in that test, to be converted; a test
    that fails on behavior is a defect in this task.
12. No diff in `src/hooks/use-job-scout.ts` or under `src/lib/`.

## Sourcing

Consistent with the Batch 05 sourcing rule, the palette is taken from a
professionally designed free source rather than hand-mixed: **Radix Colors**
(MIT) supplies the dark `gray` ink ramp and the semantic amber/red/green dark
scales, adapted to this project's token names. The citron primary is tuned by
hand against those neutrals. Both typefaces come from **Fontshare** under the ITF
Free Font Licence, which permits commercial use and self-hosting.

No component registry item is installed by this task, so the JE-015 ledger is
unchanged. The ledger governs components; this spec governs tokens and type.
