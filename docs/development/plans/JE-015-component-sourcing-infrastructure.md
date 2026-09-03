# JE-015 — Component Sourcing Infrastructure Implementation Plan

Implements
[`JE-015-component-sourcing-infrastructure.md`](../specs/JE-015-component-sourcing-infrastructure.md)
in `jobs-front`, first in Batch 05. No other Batch 05 task may start until this
one is `DONE`.

## Implementation baseline — reuse, do not rebuild

| Existing work | Current evidence | Disposition |
| --- | --- | --- |
| `jobs-front/components.json` | shadcn config, `style: "base-nova"`, `"registries": {}` | Populate `registries`; change nothing else |
| `~/.cursor/mcp.json` | User's global Cursor config with `shadcn`, `playwright`, `magic-ui`, `21st-dev` | Source of truth for server definitions; copy into a tracked `jobs-front/.mcp.json`. Do not edit the Cursor file |
| `jobs-front/.agents/skills/shadcn/` | Installed shadcn skill with `cli.md`, `mcp.md`, `registry.md` | Authoritative on registry syntax and MCP tool names; follow it, do not restate it |
| `jobs-front/.cursor/skills/job-scout-ui/SKILL.md` | UI skill whose sourcing rule names unreachable registries | Edit the sourcing rule only; leave design and QA rules intact |
| `jobs-front/node_modules/.bin/shadcn` | shadcn CLI 4.19.0, pinned in `package.json` | Use the pinned local CLI; do not add a global or differently-versioned one |
| `jobs-front/docs/design/` | Holds design reference PNGs | New home for the component source ledger |
| `jobs-front/.env.example` | Existing env documentation | Extend with the 21st.dev key; do not restructure |

## Remaining implementation

### Registry configuration

1. Add the five namespaces to `components.json` `registries`, each with a
   `{name}` placeholder. `@magicui`, `@aceternity`, `@cult-ui` and `@kokonutui`
   use the URLs published in the official index; `@reactbits` uses
   `https://reactbits.dev/r/{name}.json`.
2. Verify resolution with the pinned CLI against each namespace before writing
   the ledger. A namespace that does not resolve is reported, not silently kept.
3. Note that the CLI auto-discovers indexed namespaces and will rewrite
   `components.json` itself during an `add`. Configure explicitly anyway so the
   file is deterministic rather than a side effect of whichever component was
   installed first.

### MCP access

1. Create `jobs-front/.mcp.json` mirroring the four servers from the user's
   Cursor config, with the 21st.dev key expressed as an environment reference.
2. Document `TWENTY_FIRST_API_KEY` in `.env.example` with no value and a comment
   stating that 21st.dev degrades to unavailable without it.
3. Confirm no secret is present in the diff before finishing.

### Component source ledger

1. Enumerate the UI needs from the JE-018 through JE-021 specs. Those specs are
   authored alongside this one, so the enumeration is a read, not a guess.
2. For each need, query the configured registries through the shadcn MCP and,
   where available, the `magic-ui` MCP. Record candidates.
3. Resolve React Bits items by URL, capturing the exact TypeScript + Tailwind
   variant name rather than a base name.
4. Choose one item per need. Record the add target, install command, license,
   pulled dependencies, and Base UI/Radix provenance. Note that this project is
   Base UI (`@base-ui/react`); a Radix-based item is recorded as such so JE-018
   can apply `.agents/skills/migrate-radix-to-base/`.
5. Record needs resolved by `@shadcn` or by custom code with the reason, rather
   than forcing a premium source where none fits.
6. Omit any item whose license does not permit use here.

### Sourcing instructions

1. Rewrite the sourcing paragraph in `job-scout-ui/SKILL.md` to name the
   configured registries and point at the ledger.
2. Preserve the skill's design reference, responsive QA, and accessibility rules
   unchanged, except that the design reference images are superseded by JE-016 —
   note the dependency rather than editing the reference now.

## Test plan

This task ships configuration and documentation, so verification is executable
checks rather than unit tests:

- Each configured namespace resolves through the pinned CLI, evidenced by a
  successful search against it.
- A representative item from each namespace can be resolved without installing
  it, confirming the URL template is correct.
- With `TWENTY_FIRST_API_KEY` unset, the other four namespaces still resolve and
  21st.dev reports unavailable rather than failing the run.
- `git grep` over the diff finds no key, token, or bearer value.
- Every ledger row's add target is checked against the registry that claims it.
- `./ci.sh` passes in `jobs-front` — lint, format, build, unit, e2e — confirming
  that adding configuration broke nothing. `prettier --check .` covers the new
  JSON and Markdown, so run `pnpm format` before CI.

## Completion criteria

- Every JE-015 acceptance criterion is satisfied and evidenced.
- `./ci.sh` passes in `jobs-front`.
- The ledger covers every UI need in the JE-018 through JE-021 specs, with no
  unverified row.
- No file under `jobs-front/src/` is modified; rendered output is byte-identical.
- No secret appears in any tracked file.
- The report states explicitly whether 21st.dev was reachable during authoring.
  If it was not, the ledger says which needs were resolved without it, so the
  gap is visible rather than silent.
