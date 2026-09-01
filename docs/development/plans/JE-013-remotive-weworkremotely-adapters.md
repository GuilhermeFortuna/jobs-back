# JE-013 — Remotive and We Work Remotely Implementation Plan

Implements
[`JE-013-remotive-weworkremotely-adapters.md`](../specs/JE-013-remotive-weworkremotely-adapters.md)
after JE-012 lands provider state resolution.

## Implementation baseline — reuse, do not rebuild

| Existing work | Current evidence | Disposition |
| --- | --- | --- |
| `providers/protocol.py` | `ProgressiveProvider`, `ProviderPageBatch` | Unchanged |
| `providers/jobicy.py` | Capped-endpoint adapter with truncation warning | Follow as the pattern for Remotive |
| `providers/remoteok.py` | Bulk-response adapter yielding bounded batches | Follow as the pattern for We Work Remotely feed batching |
| `providers/himalayas.py` | Worker pool, capped retry and backoff, `Retry-After` | Follow for request discipline |
| `providers/sanitize.py` | Shared HTML sanitizer | Reuse for both adapters |
| `normalization/compensation.py` | Annualization | Reuse; extend only if free-text parsing genuinely needs it |
| `search/consolidation.py` | `dedup_key` derivation, canonical selection, source merge | Consume unchanged; add no provider-specific dedup logic |
| `providers/registry.py` | Credential requirements and state resolution from JE-012 | Register both as key-less, always-configured providers |

JE-007, JE-008, and JE-012 provider suites pass today. Existing adapter behavior
must not change.

## Remaining implementation

### Remotive

1. Implement `providers/remotive.py` mapping supported filters onto documented
   upstream parameters and leaving the rest to JE-011 index filtering.
2. Normalize identity, title, company, job type, category and tags, candidate
   location text, timestamps, and the application URL, sanitizing descriptions
   through the shared sanitizer.
3. Implement conservative free-text salary parsing: annualize only confident
   forms, never infer a currency, never expand one figure into a range, and
   leave fields null when uncertain.
4. Observe the documented result cap, report an honest `total_pages`, and emit a
   sanitized truncation warning when the cap bites.
5. Preserve Remotive attribution on every result.

### We Work Remotely

1. Implement `providers/weworkremotely.py` consuming the published feeds with a
   bounded worker pool, parsing entries defensively so one malformed entry is
   skipped rather than failing the feed.
2. Document and implement the title-and-company separation rules as data-driven
   cases with a test table, leaving unrecoverable fields null.
3. Derive `provider_job_id` from the entry's permanent identifier so identity is
   stable across fetches; assert stability by test.
4. Sanitize HTML descriptions through the shared sanitizer and leave salary
   fields null unless confidently parsed.
5. Yield entries as bounded batches with an honest `total_pages` and warn when a
   feed limit truncates coverage.
6. Preserve We Work Remotely attribution and backlink requirements on every
   result.

### Registration and budget

1. Register both keys with display names and always-configured state, and add
   them to the default enabled set.
2. Confirm the derived item budget scales with the new enabled provider count
   and that a warm default index survives fan-in across all providers.

## Test plan

- Remotive contract tests against recorded responses covering normalization,
  filter mapping, the result cap, and the truncation warning.
- Remotive salary parsing table: confident forms annualized, ambiguous forms
  null, no currency guessed, no range inferred from one figure.
- We Work Remotely feed parsing tests against recorded feeds, including a
  malformed entry skipped without failing, missing fields null, and the
  title-and-company separation table.
- Identity stability test fetching the same feed twice and asserting identical
  `provider_job_id` values.
- Attribution tests for both providers.
- Partial-failure tests for each new provider failing alone and all providers
  failing together.
- Consolidation tests for duplicates spanning a new and an existing provider,
  asserting one consolidated result with every source preserved.
- Retention test confirming the budget scales with the new provider count and a
  warm index is not evicted by added volume alone.
- Re-run of JE-005, JE-007, JE-008, JE-011, and JE-012 suites unchanged.

## Completion criteria

- Every JE-013 acceptance criterion has deterministic automated coverage.
- `./ci.sh lint` and `./ci.sh test` pass against a real PostgreSQL database.
- Both adapters use the shared sanitizer, annualizer, and consolidation path
  with no parallel implementation.
- No feed or API result is persisted and no HTML page beyond the published feeds
  is scraped.
