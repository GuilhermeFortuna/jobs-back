# JE-018 — Primitive Layer Completion Implementation Plan

Implements
[`JE-018-primitive-layer-completion.md`](../specs/JE-018-primitive-layer-completion.md)
in `jobs-front`, after JE-015, JE-016 and JE-017.

## Implementation baseline — reuse, do not rebuild

| Existing work | Current evidence | Disposition |
| --- | --- | --- |
| `jobs-front/docs/design/component-source-ledger.md` | JE-015 output | The only permitted source. Do not install an item it does not list |
| `src/components/ui/*` | 15 base-nova primitives, 4 of them unused | Extend the set; adopt the unused four; do not restyle existing ones |
| `src/app/globals.css` | JE-016 token system | Every new primitive targets these tokens |
| `src/components/job-scout/*` | 8 components holding the hand-rolled duplicates | Substitute primitives in place; preserve prop types and behavior |
| `src/hooks/use-job-scout.ts` | All state, consumed as explicit props | Untouched |
| `src/lib/search-notice.ts` | Generates every status string | Untouched; only the render location changes |
| `src/lib/api.ts` | Search page contract, `page_size: 100` | Read for the pagination wiring; do not change the contract |
| `.agents/skills/migrate-radix-to-base/` | Installed migration skill | Use when a ledger item arrives Radix-based |
| `.agents/skills/shadcn/` | Installed shadcn skill | Follow its post-install steps: fix aliases, swap icons, read every added file |

## Remaining implementation

### Installation

1. Install each primitive from the ledger with the pinned CLI. Record the exact
   commands run.
2. Read every added file. Correct hardcoded `@/components/ui/…` imports to the
   project's alias and swap icon imports to lucide.
3. Migrate any Radix-based item to Base UI before use.
4. Retarget any primitive shipping hardcoded colors onto JE-016 tokens.

### Substitution

Work one duplicate family at a time, keeping the suite green between families
rather than landing a single sweeping change:

1. `card` — job card, source card, and the three panel chrome treatments.
2. `alert` — the six banners, mapped onto the semantic tokens JE-016 added.
3. `label` / `field` / `field-description` / `field-error` — the five filter
   fields and the three profile-picker errors.
4. `dialog` — the three profile-picker forms currently built from `alert-dialog`.
   The genuine confirmation dialog for deleting a job stays an `alert-dialog`.
5. `empty` — the four empty states, moved out of the job card file into their own
   module.
6. `input-group` — the search-input pattern duplicated in two files, collapsed to
   one usage.
7. `spinner`, `skeleton` — the loading string and hand-drawn indicators.
8. `tabs` — the fake tab bar in the job detail.
9. `separator` — the border-utility dividers.
10. `scroll-area`, `tooltip` — adopt or remove; state which and why.

### Toasts

1. Introduce the toast primitive and mount it in `layout.tsx` beside the existing
   providers.
2. Move transient outcomes to it, removing each moved message from the inline
   strip so nothing is announced twice.
3. Keep the `aria-live` region and its strings intact; verify with a screen
   reader pass or an equivalent automated check that no message is read twice.

### Pagination

1. Read the existing search page contract in `src/lib/api.ts` before designing
   the interaction.
2. Wire the pagination primitive to that contract. Do not slice results client
   side and do not change `page_size` semantics.
3. If the contract cannot support the interaction, stop and report it. A backend
   change is a new task, not a workaround inside this one.

## Test plan

- Component tests for each substituted family asserting behavior is preserved:
  accessible names, roles, keyboard operation, and the labelled icon-only
  controls.
- A test asserting the three-way Save button label logic is unchanged.
- Provider filter tests asserting unconfigured providers remain unavailable and
  unselectable.
- A test asserting no message is announced twice once toasts are live, including
  the case where a toast and a status banner are visible together.
- Pagination tests against the existing page contract, asserting no client-side
  slicing.
- A check that `src/hooks/` and `src/lib/` are untouched — any diff there is a
  defect in this task.
- Full re-run of the JE-006, JE-009 and JE-014 suites, plus the JE-017 converted
  assertions, all unchanged.
- Responsive and accessibility QA at 1440×1000 and 390×844 in both themes.

## Completion criteria

- Every JE-018 acceptance criterion has automated coverage where automatable.
- `./ci.sh` passes in `jobs-front`. Run `pnpm format` first — this task touches
  many files.
- Manual end-to-end verification against a running API via `./dev.sh`: search,
  filter, paginate, save, apply, delete, and edit skills, in both themes.
- The task report lists every primitive installed, its ledger row, its exact
  install command, and the dependencies it pulled in — so the ledger can be
  reconciled against what actually landed.
- No visual redesign, layout change, or backend contract change ships with this
  task.
