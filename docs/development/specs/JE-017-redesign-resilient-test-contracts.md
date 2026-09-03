# JE-017 — Redesign-Resilient Test Contracts Specification

## Status

Proposed for Batch 05, implemented in `jobs-front`. Depends on JE-015 only, and
runs in parallel with JE-016. Both must be `DONE` before JE-018 starts.

## Purpose

Parts of the existing suite assert how the UI is built rather than what it does.
Those assertions fail on any redesign for cosmetic reasons, which makes a failing
test ambiguous exactly when the batch most needs it to be trustworthy. This task
converts them to behavioral contracts, keeping the same behavior under test, so
that a later failure means something is broken rather than something moved.

This is a prerequisite, not cleanup. It lands before any surface redesign.

## Principle

Every assertion converted here must test the same behavior afterwards. This task
does not weaken coverage, does not delete a test because it is inconvenient, and
does not replace a specific assertion with a vague one. Where an assertion is
structural because the structure genuinely is the contract — a dialog exposing
`role="dialog"`, a control being keyboard reachable — it stays.

Accessible names and roles are preferred over test IDs. A test ID is added when
no accessible query can express the target, not as the default.

## Assertions to convert

### Raw class selector

`e2e/job-scout.spec.ts` locates the search status text with
`page.locator("span.min-w-0.break-words", …)`, pinning the test to two Tailwind
utility classes on one span. Any restyle of that element breaks it. It is
replaced by a stable query for the status region.

### Heading levels

The mobile sheet test asserts the job card title is an `h3` and the detail title
an `h2`. Heading *hierarchy* is a real accessibility contract and stays under
test; the specific levels stop being asserted as literals where the redesign may
legitimately change them. The replacement asserts that the card title and detail
title are headings, are correctly nested relative to their surroundings, and
carry the expected accessible names.

### Layout breakpoint

The consolidated-detail test branches on viewport width against 1280 and asserts
the detail lives in a `role="dialog"` below it and in `role="main"` at or above.
This locks both the breakpoint value and the sheet-versus-pane architecture into
the suite. The IA is fixed for Batch 05, so the sheet-versus-pane behavior stays
under test; the hardcoded 1280 literal is replaced by a single shared constant
that the component and the test both read, so the breakpoint can move without
editing assertions.

### Base UI internal attribute

`filters-panel.test.tsx` asserts `toHaveAttribute("data-disabled", "")` on an
unavailable provider checkbox. That is a Base UI implementation detail. The
behavioral contract — the checkbox is disabled and cannot be selected — is
asserted through the accessible disabled state instead.

### Whitespace-sensitive text content

`job-card.test.tsx` and `job-detail.test.tsx` assert
`textContent === "PythonPostgreSQL"` and `=== "RustGo"` on the container labelled
`Matched skills`. Any separator, wrapper, or heading added between chips breaks
them, though nothing about the behavior changed. They are replaced by assertions
that the expected skills are present, in API order, as distinct elements — which
is the actual contract from JE-014 — while keeping the existing assertion that
the container is absent entirely when there are no matches.

### Single-alert assumptions

Four assertions use `getByRole("alert")` in the singular, relying on the status
banners being mutually exclusive. JE-021 introduces toasts, which also carry
`role="alert"`, so these break as soon as a toast and a banner coexist. Each is
scoped to the specific region under test rather than to the whole document.

### `role="article"` on the job card

The job card is queried as `role="article"`. The card remaining a landmark-ish
container is incidental; the contract is that each result is an identifiable,
individually addressable item. It is replaced by a stable per-result query that
does not constrain the element type.

### Navigation accessible names

The library test requires two navigations named exactly "Mobile navigation" and
"Main navigation", failing if the redesign consolidates them into one responsive
navigation. The contract — the current view is reachable and its active state is
exposed — is asserted without requiring two separate navigation elements.

### Exact copy matching

The suite matches a large amount of exact user-facing copy, much of it generated
in `src/lib/search-notice.ts`. Copy that is genuinely part of the contract stays
asserted. Copy asserted only incidentally, as a way to find an element, is
replaced by a role or name query. `src/lib/search-notice.test.ts` continues to
assert the generated strings directly, since there the copy *is* the unit under
test.

Related: the detail Save button is matched with the exact string `/^Save$/`,
which depends on the three-way label logic returning exactly "Save". That
assertion stays — the label logic is a real contract — but it is documented as
intentional so a later agent does not loosen it.

## Explicitly unchanged

- `src/hooks/use-job-scout.test.tsx` and every test under `src/lib/` are already
  behavioral and are not touched, except `search-params.test.ts` and
  `search-notice.test.ts` remaining as they are.
- The two Playwright projects and their viewports — Desktop Chrome 1440×1000 and
  Pixel 5 390×844 — are unchanged. Every spec continues to run twice.
- `e2e/fixtures.ts` mock data is unchanged, including the deliberately absent
  Jobicy provider and the unconfigured Adzuna provider.
- No test is deleted. No assertion is removed without an equivalent replacing it.

## Out of scope

- Any change to `src/` beyond adding test hooks and extracting the breakpoint
  constant.
- Any visual, layout, or behavior change.
- New test coverage for behavior not already covered. Batch 05's surface tasks
  add their own.

## Acceptance criteria

1. No test locates an element by Tailwind utility classes.
2. No test asserts a Base UI internal data attribute.
3. No assertion depends on the absence of whitespace between sibling elements.
4. Matched skills are asserted as distinct elements in API order, and the
   container is still asserted absent when there are no matches.
5. Alert and status assertions are scoped to a region and continue to pass when
   more than one such element is present in the document.
6. The results list and job detail are located without constraining element type
   to `article`.
7. View navigation is asserted without requiring two separate navigation
   elements.
8. The 1280 breakpoint exists as one shared constant read by both the component
   and the test; the sheet-versus-pane behavior remains asserted.
9. Heading hierarchy remains asserted; literal heading levels that the redesign
   may legitimately change are not.
10. Every behavior asserted before this task is still asserted after it, and no
    test is deleted.
11. `./ci.sh` passes in `jobs-front` with rendered output unchanged.
