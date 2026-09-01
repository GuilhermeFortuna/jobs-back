# JE-009 — Multi-Source Discovery Frontend Specification

## Status

Proposed for Batch 03. Depends on the JE-007 per-provider status contract and
the JE-008 consolidation contract. The JE-006 workspace is the baseline; this
task extends it rather than restructuring it.

## Purpose

Make multi-source results legible. A person must be able to see which provider a
role came from, which providers are still loading or degraded, and every
application link on a role that several boards list.

## Component sourcing rule

The JE-006 sourcing rule stands unchanged. Before writing a custom component,
search existing project components, then shadcn, then React Bits'
shadcn-compatible registry, then Magic UI and 21st.dev, then Aceternity or Cult
UI. Custom code is the smallest job-specific composition.

## Source attribution

- Every result card shows its source provider.
- A consolidated result indicates that several providers list the same role
  without implying several distinct roles or inflating the result count.
- Provider attribution required by a source is preserved wherever that source is
  shown, including RemoteOK's attribution and backlink requirement.
- Saved and applied snapshots show the same source information as discovery, so
  a person returning to the library still knows where a role came from.

## Per-provider search status

- The status region reports each provider by name with its own state and
  progress, alongside the existing aggregate progress, checked count, and
  nullable total.
- A search that finished while a provider failed reads as partial, not complete,
  and names the failing provider. It never reads as an empty or failed search
  when healthy providers returned results.
- A search that failed entirely remains distinguishable from a partial one.
- Existing loading, empty, offline, expired-search, and validation states from
  JE-006 keep their current behavior.

## Consolidated result detail

- The detail pane lists every source for a consolidated role, each with its own
  original and application link.
- The canonical source is identified as such, and choosing an alternate link
  never changes which snapshot a save resolves to.
- Saving or marking applied from any source produces one library entry, matching
  the JE-008 server behavior; the UI does not present a per-source save.

## Provider filtering

A provider filter lets a person restrict discovery to chosen providers. It
follows the existing filter conventions: it round-trips through the URL like the
other filters, a refresh restores it, and it can be saved into the profile's
default search alongside the rest.

## Responsive design

Source badges, per-provider status, and multi-source detail must work in the
existing three-pane desktop layout at approximately 1440×1000 and in the mobile
layout at approximately 390×844 without overflow, truncation of provider names,
or pushing primary actions out of reach. The mobile filter sheet and detail
sheet remain the mobile home for the new controls and links.

The visual references are unchanged:

- `jobs-front/docs/design/job-scout-desktop.png`
- `jobs-front/docs/design/job-scout-mobile.png`

Provider identity is conveyed by name and existing surface styling. Per-provider
brand color, logos as the primary identifier, and decorative treatments that
impede scanning are not used.

## Accessibility and states

- Per-provider status is announced through a live region without flooding
  screen-reader output on every poll.
- Source badges are readable as text, not by color alone.
- The provider filter is keyboard operable with visible focus and a clear
  accessible name.
- Alternate source links state which provider they lead to.
- Reduced-motion support and existing focus behavior are preserved.

## Out of scope

- New routes, deep links per view, or pagination UI
- Authentication, sharing, or collaborative tracking
- Per-provider branding, theming, or logo-driven identity
- Client-side deduplication or reranking of provider results
- AI ranking, semantic search, or application automation

## Acceptance criteria

1. Every result card and every library snapshot shows its source provider, and
   consolidated results indicate multiple sources without inflating counts.
2. Required provider attribution, including RemoteOK's backlink, is present
   wherever that source is displayed.
3. The status region names each provider with its own state and progress and
   presents a search that completed with a failed provider as partial.
4. The detail pane exposes every alternate source with its own original and
   application link, and saving from any source creates one library entry.
5. The provider filter round-trips through the URL, survives refresh, and can be
   saved into the profile's default search.
6. Desktop and mobile layouts absorb the new elements without overflow,
   truncated provider names, or obscured primary actions.
7. Live-region announcement, non-color-dependent badges, keyboard operation, and
   link labeling pass automated and manual checks.
8. Frontend lint, type checking, production build, component tests, and
   Playwright journeys pass.
