# JE-018 — Primitive Layer Completion Specification

## Status

Proposed for Batch 05, implemented in `jobs-front`. Depends on JE-015 for the
component source ledger, JE-016 for tokens and themes, and JE-017 for resilient
test contracts. Precedes the three surface tasks, which compose from what it
installs.

## Purpose

The workspace hand-rolls components it does not have and ignores four it does.
Three card shapes, six alert banners, five form fields, three form dialogs and
four empty states are written as raw markup, while `tabs`, `skeleton`,
`separator` and `scroll-area` sit installed and unused.

This task closes that gap so the surface tasks compose from a real primitive
layer instead of each inventing markup — which is how the eight components
diverged in the first place.

It is a de-duplication task. The diff is large; the rendered result is close to
behavior-neutral.

## Primitives to install

Sourced per the JE-015 ledger. Where the ledger resolves a need to `@shadcn`,
that is the source; where it names a premium registry item, that is the source.
No item is installed that the ledger does not list.

Needed, each with an existing hand-rolled duplicate:

| Primitive | Replaces |
| --- | --- |
| `card` | the job card, the source card, and the three panel chrome treatments |
| `alert` | six near-duplicate banners in the search status component |
| `label`, `field`, `field-description`, `field-error` | five inline label copies in the filters panel and three inline error copies in the profile picker |
| `dialog` | three form dialogs currently built from `alert-dialog` |
| `empty` | four hand-rolled empty states, three of them living inside the job card file |
| `sonner` or an equivalent toast | transient outcomes currently funnelled into one inline text line |
| `pagination` | nothing — results are an unbounded list today |
| `spinner` | the loading indicators drawn by hand |
| `input-group` | the search-input-with-leading-icon pattern, duplicated verbatim in two files |

Needed for the surface tasks, without a current duplicate: `popover`, `command`,
`slider`, `accordion`, `toggle-group`, `switch`.

Installation constraints:

- Every installed primitive is Base UI, matching the existing `base-nova` files.
  A ledger item that arrives Radix-based is migrated using the installed
  `migrate-radix-to-base` skill before use.
- Installed files are read after installation. Hardcoded `@/components/ui/…`
  imports are corrected to the project's alias, and icon imports are swapped to
  lucide, the project's configured icon library.
- Every primitive consumes JE-016 tokens. A primitive that ships its own
  hardcoded colors is retargeted before it is used.

## Adoption of unused primitives

- `tabs` replaces the fake tab bar in the job detail, currently a `span` with a
  bottom border imitating a single selected tab.
- `skeleton` replaces the bare "Loading roles…" string.
- `separator` replaces the `border-y` and `border-t` utility dividers.
- `scroll-area` is adopted where the panes scroll, or is removed if it earns no
  place. Leaving it installed and unused is not an outcome.
- `tooltip` is mounted as a provider with no tooltip ever rendered. The icon-only
  controls that the UI skill requires to be labelled get real tooltips, or the
  provider is removed.

## Behavior that must not change

This task substitutes components. It does not redesign. In particular:

- The state layer is untouched. `use-job-scout.ts` and every module under
  `src/lib/` are consumed as they are. Component prop types and the
  `DEFAULT_FILTERS` export are preserved.
- Accessible names, roles, and keyboard operation are preserved. Replacing the
  hand-rolled checkbox rows, the tag input, and the icon buttons must not lose
  the labels and keyboard removal that JE-014 established.
- The three-way Save button label logic is preserved exactly.
- Provider filtering, including unconfigured providers rendering as unavailable
  and unselectable, is preserved.
- The `aria-live` announcement region and the announced strings are preserved.

## Toasts and the status region

Introducing toasts creates two elements that can carry `role="alert"`
simultaneously. JE-017 scopes the affected assertions; this task must not
reintroduce the ambiguity by announcing the same message twice. A message
promoted to a toast is removed from the inline strip, or the toast is marked so
that assistive technology does not read it twice.

The strings themselves are generated in `src/lib/search-notice.ts` and remain
generated there. This task changes where they render, not what they say.

## Pagination

The results list is unbounded today, with a page size of 100 hardcoded in the API
layer. The design reference shows pagination. This task installs the primitive
and wires it to the existing search page contract without changing that contract.
If the backend page contract cannot support the interaction, the finding is
reported rather than worked around with client-side slicing.

## Out of scope

- Visual redesign of any surface. Composition and tokens only.
- Layout or information architecture changes.
- Backend contract changes of any kind.
- Installing primitives no Batch 05 spec needs.

## Acceptance criteria

1. Every primitive listed above exists in `src/components/ui/`, sourced per the
   ledger, and no primitive is installed that the ledger does not list.
2. Every installed primitive is Base UI, uses the project's import alias, and
   uses lucide icons.
3. Every installed primitive is driven by JE-016 tokens, with no hardcoded color.
4. The three card shapes, six alert banners, five inline labels, three inline
   errors, three form dialogs, four empty states, and the duplicated
   search-input pattern are each replaced by a primitive.
5. `tabs`, `skeleton` and `separator` are adopted; `scroll-area` and `tooltip`
   are either adopted or removed.
6. The empty states no longer live inside the job card file.
7. Component prop types, the `DEFAULT_FILTERS` export, `use-job-scout.ts` and
   every `src/lib/` module are unchanged.
8. Accessible names, roles, keyboard operation, and the `aria-live` region are
   preserved; icon-only controls remain labelled.
9. No message is announced twice once toasts are introduced.
10. Pagination is wired to the existing search page contract, with no client-side
    slicing and no backend contract change.
11. All JE-006, JE-009, and JE-014 behavior passes unchanged.
12. Responsive and accessibility QA passes at both supported breakpoints in both
    themes.
