# JE-016 — Design System Foundation Specification

## Status

Proposed for Batch 05, implemented in `jobs-front`. Depends on JE-015 for the
component source ledger. Establishes the visual target every later Batch 05 task
builds against.

## Purpose

The workspace has no design system. It has stock shadcn tokens, four brand
overrides, and 89 hardcoded hex literals spread across eight components. This
task replaces that with a token layer expressive enough that a redesign can be
carried out by editing tokens and composing components rather than by writing
colors into markup.

It also ships the visual target itself. Four surface tasks redesigning four
surfaces against no shared reference will diverge; that divergence is the
failure this task exists to prevent.

## Current state being replaced

- `src/app/globals.css` overrides four values on top of the stock shadcn set:
  `--background: #f7f8fb`, `--foreground: #101936`, `--primary: #3d49df`, and
  `--radius: 0.875rem`. Everything else is the default neutral palette.
- There are no shadow, spacing, type-scale, or motion tokens. Elevation exists
  as two inline `shadow-[…]` arbitrary values in `job-card.tsx`.
- `--font-display` is wired to Fraunces in `layout.tsx` and used by nothing;
  `--font-heading` is aliased to `--font-sans`.
- `.dark` is defined but unreachable: it is the untouched neutral shadcn dark
  palette with the brand color absent, no theme provider or toggle exists, and
  `globals.css` hardcodes a light `body` background that would override it.
- 89 hex literals live in components. `#3d49df` appears 27 times, `#6d7690` nine
  times, `#5964ed` nine times.

## Visual direction

Premium, distinctive, and animated, with the animation placed deliberately.

The working surfaces — filters, results list, job detail — stay dense, quiet and
legible. They are read for long stretches, on desktop and on mobile. Expressive
and animated components are placed where a user passes through rather than
dwells: a restrained ambient treatment in the header band that fades into the
working surface, the empty and first-run states, the search-in-progress state,
and the profile and skills surface.

Every animated treatment has a static fallback. `globals.css` already ships a
global `prefers-reduced-motion` kill-switch for animations and transitions; a
treatment that becomes invisible or broken when that rule applies is not
acceptable. Effects that cost meaningfully on a mid-range mobile device degrade
to a static equivalent at mobile breakpoints.

## Token layer

The `@theme` block is extended from a color-only alias list into a complete
system. Required token families:

- **Color.** A full semantic palette carrying the brand identity in *both*
  themes. The dark theme is designed, not inherited: it may not ship the stock
  neutral palette with the brand color absent. Semantic roles that components
  currently inline — success, warning, info, and the applied-action accent
  currently written as `#f26450` — become named tokens.
- **Elevation.** A shadow scale replacing the two inline arbitrary values, with
  values tuned separately per theme, since a light-theme shadow reads as noise on
  a dark surface.
- **Typography.** A type scale with named steps. Fraunces is already loaded and
  paid for on every page load; either it earns its place through `--font-display`
  being genuinely used, or it is removed from `layout.tsx`. Shipping an unused
  webfont is not an outcome.
- **Radius.** The existing `--radius`-derived scale is kept; its base value may
  change with the direction.
- **Motion.** Duration and easing tokens, so that transition timing is
  consistent and adjustable in one place rather than per component.

## Theme switching

- Light, dark, and system, with system as the default.
- An explicit toggle exposing all three states. Its placement in the header is
  specified by JE-019; this task delivers the control and the mechanism.
- No flash of incorrect theme on first paint. A blocking inline script or the
  equivalent from the chosen library is required.
- The selected preference persists across reloads.
- The hardcoded light `body` background in `globals.css` is removed, since it
  defeats the dark theme.
- Following the system preference means responding to it changing while the app
  is open, not only at load.
- Both themes meet WCAG AA contrast for text and for interactive controls.

## Hex literal elimination

All 89 hardcoded hex literals are replaced by tokens. This includes:

- the brand blue `#3d49df` in all 27 occurrences;
- muted text `#6d7690` and the focus ring `#5964ed`;
- the six alert banner color families in `search-status.tsx`;
- the applied-action accent `#f26450` and the destructive `#b34438`;
- the success green used for the salary pill;
- the `[&_[data-slot=progress-indicator]]:bg-[#3d49df]` selector reaching into
  the Progress primitive's internals, which a token-driven primitive removes.

The eight-times-repeated hand-written focus ring string is replaced by a single
token-driven treatment.

Hex literals may remain only inside token definitions in `globals.css`.

## Design reference

The task ships rendered references replacing `docs/design/job-scout-desktop.png`
and `docs/design/job-scout-mobile.png`, captured in both themes at the project's
supported breakpoints — 1440×1000 and 390×844. Superseded references are removed
rather than left alongside the new ones, so no later task builds against a stale
target.

A short written statement of the direction accompanies them: what the surfaces
are, where animation is and is not used, and what the fallbacks are.

## Out of scope

- Redesigning any surface. Component markup changes only where a hex literal or
  focus ring string is replaced by a token.
- Installing feature components from the ledger. That is JE-018.
- Layout, spacing, or information architecture changes.
- Backend contract changes of any kind.

## Acceptance criteria

1. The `@theme` layer defines color, elevation, typography, radius, and motion
   token families, and both light and dark palettes carry the brand identity.
2. Semantic tokens exist for success, warning, info, destructive, and the
   applied-action accent.
3. Theme switching offers light, dark, and system; system is the default;
   the preference persists across reloads.
4. No flash of incorrect theme occurs on first paint in either theme.
5. A system preference changed while the app is open is reflected without a
   reload.
6. The hardcoded `body` background is removed from `globals.css`.
7. Zero hex literals remain outside token definitions, verifiable by grep across
   `src/`.
8. The repeated hand-written focus ring string is replaced by one token-driven
   treatment.
9. The Progress primitive is themed by token, with no arbitrary child selector
   reaching into its internals.
10. Both themes meet WCAG AA contrast for text and interactive controls.
11. Every animated treatment introduced has a static fallback under
    `prefers-reduced-motion` and remains legible when that rule applies.
12. Fraunces is either used through `--font-display` or removed from
    `layout.tsx`.
13. New design references exist for both themes at both breakpoints, and the
    superseded references are removed.
14. All JE-006, JE-009, and JE-014 behavior is unchanged: search, filters, URL
    restore, save and apply flows, per-provider status, and skills editing.
