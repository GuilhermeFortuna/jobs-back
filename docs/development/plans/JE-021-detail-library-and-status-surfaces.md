# JE-021 — Detail, Library and Status Surfaces Implementation Plan

Implements
[`JE-021-detail-library-and-status-surfaces.md`](../specs/JE-021-detail-library-and-status-surfaces.md)
in `jobs-front`, after JE-019. Runs in parallel with JE-020; the two own disjoint
files. Last task in Batch 05.

## Implementation baseline — reuse, do not rebuild

| Existing work | Current evidence | Disposition |
| --- | --- | --- |
| `src/components/job-scout/job-detail.tsx` | Header, meta, badges, action bar, fake tab bar, description, sources, attribution, footer | Rebuild on JE-018 primitives; preserve every accessible name and the Save label logic |
| `src/components/job-scout/search-status.tsx` | Six banner blocks, notice line, per-provider list, progress bar, `aria-live` region | Collapse the banners to one `alert` with variants; keep the live region intact |
| `src/components/job-scout/profile-picker.tsx` | Picker plus create, rename and skills dialogs built on `alert-dialog` | Move the three forms to `dialog`; rebuild the skills editor on the ledger tag input |
| `src/components/job-scout/delete-job-dialog.tsx` | Genuine confirmation | Stays an `alert-dialog`; token substitution only |
| `src/lib/search-notice.ts` | Generates every status string and the announcement key | Untouched. Render differently, say the same thing |
| `src/lib/providers.ts` | `REMOTEOK_ATTRIBUTION`, `providerJobUrl`, `providerApplyUrl`, `failedProviderNames` | Reuse for attribution and source links |
| `src/lib/skills.ts` | `MAX_SKILLS`, `MAX_SKILL_LABEL_LENGTH`, `validateSkillLabel` | Reuse for the client guards; do not restate the rules |
| `src/hooks/use-job-scout.ts` | `updateSkills`, save/apply/delete actions | Untouched |
| Logo component from JE-020 | Card-side logo with letter-tile fallback | Reuse it here. Do not write a second one |
| `jobs-front/docs/design/` | JE-015 ledger, JE-016 references | Only permitted component source; the visual target |

## Coordination with JE-020

Both tasks touch empty states and both need the logo component. To avoid two
divergent treatments:

- JE-020 lands the logo component and the results-side empty states first.
- This task consumes both. If it starts before JE-020 lands them, it waits rather
  than writing its own.
- If the two run concurrently and diverge, JE-020's version is authoritative.

## Remaining implementation

### Job detail

1. Replace the fake tab bar with real tabs and divide the content across them.
2. Adopt the shared logo component; delete the second letter-tile copy.
3. Rebuild the source list on `card`, preserving link accessible names and the
   primary-source designation.
4. Rebuild the action bar. Keep the three-way Save label logic byte-for-byte and
   move the applied action to the accent token.
5. Verify saved snapshots still render when the provider has dropped the listing.

### Search status

1. Collapse the six banners into one `alert` with variants mapped to the JE-016
   semantic tokens.
2. Keep the `aria-live` region and the strings from `search-notice.ts`.
3. Rebuild the per-provider status list on semantic tokens, preserving the
   loading, complete and failed distinction.
4. Add the expressive search-in-progress treatment from the ledger. Verify every
   piece of information it replaces is still present: progress, roles checked,
   per-provider status, partial results and warnings.
5. Implement reduced-motion and mobile fallbacks and confirm the status stays
   fully legible under both.
6. Audit toast versus inline messaging so nothing is announced twice.

### Profile and skills

1. Move create, rename and edit-skills to `dialog`. Leave the job-delete
   confirmation on `alert-dialog`.
2. Rebuild the skills editor on the ledger tag input, walking the JE-014
   contract point by point and asserting each one.
3. Rebuild the three inline errors on `field-error`, reusing `validateSkillLabel`
   rather than restating the rules.
4. Add the expressive treatment with its fallbacks.

## Test plan

- Tab tests: content divided across tabs, keyboard operable, correct roles.
- Logo tests confirming one shared component serves both card and detail.
- A test asserting the three-way Save label logic is unchanged.
- Attribution tests for every provider including RemoteOK, and source-link
  accessible names with the primary source designated.
- A saved-snapshot test for a listing the provider has removed.
- Alert variant tests covering all six former banner states.
- A test asserting no message is announced twice with a toast and a banner
  visible together.
- Live-region tests asserting the announced strings are unchanged from
  `search-notice.ts`.
- A test asserting exact totals appear only when a search is complete.
- Reduced-motion tests asserting the search-in-progress treatment stays legible
  and loses no information.
- The full JE-014 skills suite: add, remove, keyboard removal, persistence,
  labels-only payload, wholesale replacement, cap, length, duplicates, 422 as
  readable text, empty list valid, re-rank statement present.
- Save, apply, delete and unsaved-detail resolution tests.
- Full re-run of the JE-006, JE-009 and JE-014 suites and the JE-017 converted
  assertions.
- Visual QA at 1440×1000 and 390×844 in both themes against the JE-016
  references.

## Completion criteria

- Every JE-021 acceptance criterion has automated coverage where automatable.
- `./ci.sh` passes in `jobs-front`; run `pnpm format` first.
- Manual end-to-end verification against a running API via `./dev.sh`: run a
  search and watch the in-progress treatment with a real provider failing, open
  a consolidated result and check every source, save, apply, delete, and edit
  skills — in both themes.
- `use-job-scout.ts` and every `src/lib/` module are unchanged.
- Empty-state treatment matches JE-020's, with one shared implementation.
- With this task `DONE`, Batch 05 is complete: no hand-rolled duplicate of an
  available primitive remains, and no hardcoded color remains outside
  `globals.css`.
