# JE-017 — Redesign-Resilient Test Contracts Implementation Plan

Implements
[`JE-017-redesign-resilient-test-contracts.md`](../specs/JE-017-redesign-resilient-test-contracts.md)
in `jobs-front`. Runs in parallel with JE-016; both precede JE-018.

## Implementation baseline — reuse, do not rebuild

| Existing work | Current evidence | Disposition |
| --- | --- | --- |
| `e2e/job-scout.spec.ts` | Six specs run against both viewport projects | Convert the coupled locators in place; keep every scenario and its coverage |
| `e2e/fixtures.ts` | Mock profile, providers, consolidated job, search pages | Unchanged. Do not add fixtures for this task |
| `playwright.config.ts` | Desktop 1440×1000 and Pixel 5 390×844, production `next start` on 3014 | Unchanged |
| `src/components/job-scout/*.test.tsx` | Five component suites | Convert only the assertions named in the spec |
| `src/hooks/use-job-scout.test.tsx`, `src/lib/*.test.ts` | Behavioral, no DOM coupling | Unchanged |
| `src/components/job-scout/index.tsx` | Holds the `window.innerWidth < 1280` check and the `xl:` classes | Extract the breakpoint to one shared constant; change nothing else |
| `src/lib/` | Pure logic modules | Home for the shared breakpoint constant, following existing module conventions |

## Remaining implementation

1. Extract the 1280 breakpoint into a single exported constant in `src/lib/`,
   consumed by `index.tsx` and by the e2e spec. The Tailwind `xl:` classes and
   the JS check must agree with it; if they cannot both read the constant,
   document how they are kept in sync.
2. Replace the `span.min-w-0.break-words` locator with a query for the search
   status region, adding a test hook only if no accessible query reaches it.
3. Rework the heading assertions to check hierarchy and accessible names rather
   than literal levels.
4. Replace the Base UI `data-disabled` assertion with the accessible disabled
   state.
5. Rewrite the two matched-skills assertions to check for distinct elements in
   API order, preserving the empty-list absence assertion exactly.
6. Scope each of the four `getByRole("alert")` assertions, and the `role="status"`
   assertions that share the problem, to the region under test.
7. Replace the `role="article"` query with a per-result query that does not
   constrain element type.
8. Rework the navigation assertions so a single responsive navigation would
   satisfy them, while still asserting the active view is exposed.
9. Audit remaining exact-copy matches. Keep copy that is the contract; replace
   copy used only as a locator. Leave `search-notice.test.ts` alone.
10. Annotate the `/^Save$/` assertion as intentional, naming the three-way label
    logic it protects.

## Test plan

The suite is the subject, so verification is about proving equivalence:

- Every converted assertion is run against the current, un-redesigned UI and
  passes. A conversion that only passes after a redesign has changed the
  contract.
- A before-and-after inventory of asserted behaviors, demonstrating the sets are
  identical. This is the primary evidence for acceptance criterion 10.
- Both Playwright projects pass, so mobile and desktop branches are both
  exercised.
- Unit suites pass unchanged where untouched — any diff in
  `use-job-scout.test.tsx` or `src/lib/` results is a defect in this task.
- A deliberate check that the alert scoping works when two `role="alert"`
  elements coexist, since that is the future condition it exists for. Simulate it
  in the component test rather than waiting for JE-021.

## Completion criteria

- Every JE-017 acceptance criterion is satisfied.
- `./ci.sh` passes in `jobs-front`.
- Rendered output is unchanged: the only `src/` diff is the extracted breakpoint
  constant and any test hooks that could not be avoided.
- The before-and-after behavior inventory is included in the task report.
- The report names every test hook added and why an accessible query could not
  serve instead. A long list of test IDs indicates the accessible-query-first
  rule was not followed and is grounds for rework.
