# JE-009 — Multi-Source Discovery Frontend Implementation Plan

Implements
[`JE-009-multi-source-discovery-frontend.md`](../specs/JE-009-multi-source-discovery-frontend.md)
once the JE-007 and JE-008 API contracts are final. Implementation is in
`jobs-front` on a branch of the same name.

## Implementation baseline — reuse, do not rebuild

| Existing work | Current evidence | Disposition |
| --- | --- | --- |
| `src/hooks/use-job-scout.ts` | Boot sequence, 900 ms poll loop with generation counters, `keepStale` refresh handling, `statusKind` state machine, save/apply/delete | Extend the status derivation and filter state; do not restructure the hook or introduce a state library |
| `src/lib/api.ts` | Typed mirror of backend schemas | Extend with per-provider status and `alternate_sources`; keep it a mirror, not a second model |
| `src/lib/search-params.ts` | URL and filter round-trip via `syncFiltersToUrl` | Extend with the provider filter using the existing conventions |
| `src/components/job-scout/search-status.tsx` | Aggregate progress, checked count, warnings, offline and expired states | Extend with per-provider rows and the partial state |
| `src/components/job-scout/job-card.tsx` | Card layout, saved/applied state, `EmptyState` | Extend with the source badge |
| `src/components/job-scout/job-detail.tsx` | Description, attribution, apply action | Extend with the alternate source list |
| `src/components/job-scout/filters-panel.tsx` | Filter controls and default-search save | Extend with the provider filter |
| `src/components/ui/*` | 14 shadcn primitives already vendored | Use for badges, filter controls, and status rows before sourcing anything new |
| `e2e/fixtures.ts` | Fully mocked `window.fetch` driving four Playwright journeys | Extend fixtures with multi-provider and consolidated payloads |

The frontend suite passes today: `use-job-scout.test.tsx`, the `src/lib`
tests, and the four Playwright journeys in `e2e/job-scout.spec.ts` across the
desktop and Pixel 5 projects. Those journeys must keep passing; the search
payload gains fields rather than changing shape.

## Remaining implementation

### API contract and state

1. Mirror the JE-007 per-provider status block, `is_partial`, and the JE-008
   `alternate_sources` shape in `src/lib/api.ts` before touching components.
2. Derive a partial state in the hook's `statusKind` machine so a completed
   search with a failed provider is neither `complete` nor `failed`, and keep
   the existing `offline`, `expired`, `empty`, and `validation` behavior intact.
3. Keep per-provider status inside the existing poll loop and generation-counter
   cancellation; do not add a second polling path.
4. Preserve the selected result across progressive pages when consolidation
   merges the selected item into another entry.
5. Extend the provider filter through the existing filter state, URL
   round-trip, and default-search save without special-casing it.

### Source attribution and status

1. Add a source badge to the result card that reads as text and names the
   canonical provider, indicating additional sources without implying additional
   roles.
2. Extend the status region with per-provider rows showing name, state, and
   progress alongside the aggregate figures.
3. Present a partial search explicitly, naming the failing provider, and keep it
   visually distinct from a fully failed search and from an empty result.
4. Announce status changes through a live region that reports meaningful
   transitions rather than every poll.
5. Carry required provider attribution, including RemoteOK's backlink, into
   every surface that displays that source.

### Library and detail surfaces

1. List every alternate source in the detail pane with its own original and
   application link, each labeled with its provider.
2. Identify the canonical source, and keep saving a single action that resolves
   server-side regardless of which source link the person opened.
3. Show the same source information on saved and applied snapshots, using the
   `alternate_sources` returned by the library API.
4. Confirm repeated saving of a consolidated role still reads as success in the
   UI, matching the JE-008 server behavior.

### Responsive and accessibility pass

1. Verify the three-pane desktop layout and the mobile filter and detail sheets
   at the reference viewports with several providers and multi-source results.
2. Prevent provider-name truncation and overflow in the status region and on
   cards at the narrow viewport.
3. Confirm keyboard operation, visible focus, and accessible names for the
   provider filter and every alternate source link.
4. Preserve reduced-motion behavior and existing focus management in both
   sheets.

## Test and QA plan

- Vitest coverage for partial-state derivation in `use-job-scout.ts`, including
  a completed search with one failed provider and an all-failed search.
- Vitest coverage for the provider filter round-trip through
  `search-params.ts` and for saving it into profile defaults.
- Component tests for the source badge, the per-provider status rows, and the
  alternate source list rendering every link.
- Playwright journey for a degraded-provider search reading as partial and
  naming the provider.
- Playwright journey opening a consolidated result, inspecting every source, and
  saving once to produce one library entry.
- Mobile checks in the existing Pixel 5 project for the filter sheet and detail
  sheet with multi-source content.
- Accessibility checks for live-region announcement volume, non-color-dependent
  badges, focus, and link labeling.
- `./ci.sh` in `jobs-front`, and a manual pass against a running backend through
  `./dev.sh` with more than one provider enabled.

## Completion criteria

- Every JE-009 acceptance criterion has automated or recorded manual coverage.
- `./ci.sh` in `jobs-front` passes, including lint, Prettier, production build,
  vitest, and Playwright on both projects.
- Desktop and mobile reference viewports are verified with multiple providers
  and at least one consolidated result.
- No new routes, pagination UI, client-side deduplication, provider branding, or
  authentication behavior is added.
