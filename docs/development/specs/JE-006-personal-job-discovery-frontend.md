# JE-006 — Personal Job Discovery Frontend Specification

## Status

In progress for Batch 02. Depends on JE-004 and JE-005 API contracts. The
existing scaffold is an implementation baseline, not an accepted completion.

## Purpose

Provide one focused personal workspace for live discovery and a profile-specific
saved/applied library. The interface is optimized for the owner and trusted
people with separate profiles, not for public signup or multi-tenant operation.

## Component sourcing rule

Before writing a custom component, search in this order:

1. existing project components;
2. shadcn;
3. React Bits' shadcn-compatible registry;
4. Magic UI and 21st.dev;
5. Aceternity or Cult UI.

Use a public component when it meets the behavior and accessibility need.
Custom code should be the smallest job-specific composition. Component license
analysis is not part of this project.

## Application structure

The persistent top-level views are:

- `Discover` — live provider results;
- `Saved` — selected profile's saved snapshots;
- `Applied` — selected profile's applied snapshots.

A profile picker is always reachable. The browser remembers the selected profile
locally and falls back predictably if it was removed. Users can create and rename
profiles without authentication UI.

## Discover experience

- Initialize controls from URL parameters when present, otherwise from the
  profile's default search.
- Keep meaningful filters and sort in the URL so a refresh restores the view.
- Let the user replace the selected profile's default search explicitly.
- Show provider name, progress, checked count, partial results, warnings, and an
  exact total only after completion.
- Keep stale results visible during a default-search refresh.
- Preserve the selected result when progressive pages arrive when possible.
- Resolve an unsaved detail using `search_id`, provider, and provider job ID so
  saving can request an authoritative backend snapshot.

Result cards show company, title, location/eligibility, compensation when known,
employment type, seniority, posting age, and saved/applied state. Detail shows
the normalized description, source attribution, original/application link, and
actions to save or mark applied.

## Library experience

- Saved and Applied lists are profile-isolated and use durable snapshot IDs.
- Either state can move to the other state.
- Either state can be permanently deleted after an explicit confirmation.
- The UI treats repeated save as success, not as an unrecoverable conflict.
- A removed provider listing remains readable from its saved snapshot.

## Responsive design

Desktop at approximately 1440×1000 uses filters, result list, and detail as a
three-pane workspace. Mobile at approximately 390×844 uses compact navigation,
a filter sheet, card-first results, and a full-height detail sheet.

The visual references are:

- `jobs-front/docs/design/job-scout-desktop.png`
- `jobs-front/docs/design/job-scout-mobile.png`

Use cool off-white, white surfaces, deep navy type, indigo primary actions, and
warm coral only for applied actions. Avoid marketing-page composition,
decorative effects that impede scanning, excessive pills, and fabricated data
or metrics outside an explicitly labeled development preview.

## Accessibility and states

- Keyboard access and visible focus for all controls and cards
- Labels or tooltips for icon-only controls
- Reduced-motion support
- Accessible dialogs/sheets and deletion confirmation
- Loading, partial, empty, provider-warning, API-offline, expired-search, and
  validation-error states
- No raw provider HTML injected without sanitization

## Out of scope

- Login, signup, invitations, or account recovery
- Shared libraries or collaborative workflows
- Notes, reminders, messaging, AI ranking, or application automation
- A marketing site or public provider catalog

## Acceptance criteria

1. Profile selection is remembered and all searches/preferences/library actions
   operate on that profile only.
2. URL parameters restore discover filters and an explicit action saves them as
   profile defaults.
3. Progressive results, nullable/exact totals, stale refresh, and warnings are
   represented accurately.
4. Save, apply, reverse-state, and confirmed permanent deletion work end to end.
5. Desktop and mobile layouts match the supplied references in hierarchy and
   behavior without overflow or obscured actions.
6. Core keyboard, focus, labeling, reduced-motion, empty, and error behaviors
   pass automated and manual checks.
7. Frontend lint, type checking, production build, component tests, and
   Playwright journeys pass.

