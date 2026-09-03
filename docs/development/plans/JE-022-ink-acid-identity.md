# JE-022 — Ink and Acid Visual Identity Implementation Plan

Implements [`JE-022-ink-acid-identity.md`](../specs/JE-022-ink-acid-identity.md)
in `jobs-front`, after JE-021. It re-skins finished surfaces, so it must not
start while JE-020 or JE-021 is open — a token change landing under an in-flight
restyle makes both undiagnosable.

## Implementation baseline — reuse, do not rebuild

| Existing work | Current evidence | Disposition |
| --- | --- | --- |
| `src/app/globals.css` | JE-016 `:root` / `.dark` token blocks | Substitute values in place; the token *names* and the `@theme` mapping stay |
| `src/app/layout.tsx` | `next/font/google` — Fraunces + Geist | Swap loader and faces only; provider tree untouched |
| `src/components/job-scout/header-ambient.tsx` | Reads `--primary`; animated/static split | Retune opacity only; the hue already follows the token |
| `src/components/job-scout/job-card.tsx` | Applied at `:39`, badge at `:127-128` | Three named edits; no restructure |
| JE-016 theme mechanism | Provider, three-state control, no-flash | Untouched — values change, mechanism does not |
| JE-017 behavioral contracts | Structure-decoupled assertions | Run them; they should survive a pure re-skin |
| `src/hooks/use-job-scout.ts`, `src/lib/*` | State and pure logic | Untouched (Batch 05 rule 6) |
| `docs/design/component-source-ledger.md` | JE-015 output | Unchanged — this task installs no components |

## Token values

Authored dark-first. Light is derived afterward from these, not in parallel.

### `.dark` — authored

| Token | Value | Note |
| --- | --- | --- |
| `--background` | `#0a0a0b` | Ink, no hue tint |
| `--surface` | `#101011` | |
| `--card` / `--popover` | `#131314` | |
| `--secondary` / `--muted` | `#1a1a1c` | Raised neutral — secondary actions |
| `--foreground` / `--card-foreground` | `#ececee` | |
| `--muted-foreground` | `#8b8b91` | |
| `--border` / `--input` | `#26262a` | |
| `--primary` | `#c6f24a` | Acid citron |
| `--primary-foreground` | `#161c05` | Text on citron fill |
| `--primary-hover` | `#d2f56d` | |
| `--primary-soft` | `#1b2109` | |
| `--primary-border` | `#4b621c` | |
| `--ring` | `#a8d63a` | |
| `--applied` | `#c6f24a` | Outline, never fill |
| `--applied-foreground` | `#c6f24a` | Citron text — corrects the `text-destructive` bug |
| `--applied-soft` | `#161a08` | |
| `--applied-border` | `#68872b` | Outline and the 3px left rule |
| `--data-foreground` | `#d8d4cd` | **New pair** — salary and numeric data |
| `--data-border` | `#3a3a34` | |
| `--success` / `-soft` / `-border` | `#6fd39b` / `#0d1a13` / `#1f4433` | Confirmations only |
| `--warning` / `-soft` / `-border` | `#f5b76a` / `#1a1207` / `#4a3312` | |
| `--destructive` / `-foreground` / `-soft` / `-border` | `#f78a8a` / `#1c0f10` / `#190d0e` / `#4d2124` | |
| `--brand-mark` | `#ececee` | |

`--chart-1..5` re-derive from the above; coral and indigo values are removed.

### `:root` — derived

Warm-neutral paper, not blue. `--primary` stays `#c6f24a` with
`--primary-foreground: #161c05`, so citron-as-fill is identical across themes.
Add `--primary-emphasis` (deeper olive-citron) for **citron-as-text**, which
fails AA on light backgrounds — every light-mode use of citron as text or icon
resolves to it. Dark mode does not define the split.

## Steps

1. **Add the fonts.** Download the General Sans and Cabinet Grotesk `woff2`
   files from Fontshare into `src/app/fonts/`, with the ITF licence text
   alongside. Rewrite `layout.tsx` to load both via `next/font/local`, keeping
   `--font-sans` / `--font-display` and the existing `cn()` variable wiring.
   Verify no `next/font/google` import and no font-CDN request remains.
2. **Author `.dark`.** Substitute the table above into the `.dark` block, adding
   the `--data-*` pair and its `@theme` mapping beside the existing pairs.
3. **Retune the ambient band.** Lower `maxOpacity` on the animated grid and the
   static fallback's `opacity-[…]` until the band reads ambient against ink.
   Check all three paths: `sm+` animated, mobile static, reduced-motion static.
4. **Land the three markup edits** in `job-card.tsx` (and `job-detail.tsx` where
   it mirrors them):
   - salary chip onto `--data-*`;
   - applied badge onto the applied token pair, removing `text-destructive`;
   - applied rows get the 3px citron left rule and the "Applied" tag, with the
     applied action rendered as citron outline rather than fill.
   Keep the accessible name; the rule and tag are additive cues, so applied is
   never conveyed by color alone.
5. **Derive `:root`.** Only after dark is settled. Introduce `--primary-emphasis`
   and route every light-mode citron-as-text use through it.
6. **Sweep for hardcoded color.** `grep -rnE '#[0-9a-fA-F]{3,8}' src/components
   src/app --include='*.tsx'` must return nothing outside `globals.css` and the
   ambient component's token reads.
7. **Rewrite `docs/design/visual-direction.md`** for this identity: surfaces,
   the single-accent tiering rule, the type pairing and its self-hosted loading,
   and a regenerated AA table.
8. **Recapture the four reference screenshots** at 1440×1000 and 390×844.

## Verification

| Check | Command / method |
| --- | --- |
| Unit and component contracts | `pnpm test` — JE-017 contracts pass unchanged |
| E2E | `pnpm test:e2e` |
| Lint and types | `pnpm lint && pnpm typecheck` |
| No hardcoded color | the `grep` in step 6 returns nothing |
| No forbidden diff | `git diff --name-only` shows no `src/hooks/use-job-scout.ts`, no `src/lib/*` |
| Fonts self-hosted | build output contains the local `woff2`; devtools network shows no font CDN |
| Contrast | every pair in the rewritten AA table measured, both themes |
| Theme mechanism intact | reload in light, dark and system with no flash of incorrect theme |

## Completion criteria

1. Every acceptance criterion in the spec is satisfied.
2. `pnpm test`, `pnpm test:e2e`, `pnpm lint` and `pnpm typecheck` pass.
3. No coral or indigo value remains anywhere in `jobs-front`.
4. `visual-direction.md` and all four reference screenshots reflect the shipped
   identity.
5. `git diff` touches no backend file, no `src/lib/` module, and not
   `use-job-scout.ts`.

## Risks

- **A test asserting a JE-016 color.** Per spec criterion 11, convert it to a
  behavioral assertion; do not restore the old value to make it pass.
- **Citron over-application.** A single high-chroma accent tolerates far less
  surface area than a two-accent palette. If more than roughly three things carry
  citron on one screen, the extras go neutral.
- **The applied outline reading too quietly** despite the left rule. Report it as
  a finding with a screenshot rather than reaching for a second accent — that
  would undo the identity decision this task exists to implement.
