# JE-015 — Component Sourcing Infrastructure Specification

## Status

Proposed for Batch 05, implemented in `jobs-front`. Depends on nothing. First
task in the batch; every other Batch 05 task consumes its output.

## Purpose

Batch 02 and Batch 03 instructed agents to source UI from premium component
registries. No registry was ever configured, so no agent could comply. This task
makes the instruction executable and records what may be used, before any
redesign work begins.

## Problem being corrected

Three facts combined to guarantee the failure:

1. `jobs-front/components.json` contains `"registries": {}` — no registry is
   configured beyond the built-in `@shadcn`.
2. The installed shadcn skill
   (`jobs-front/.agents/skills/shadcn/SKILL.md`, workflow step 8) states:
   *"Registry must be explicit — do not guess the registry. If no registry is
   specified… ask which registry to use. Never default to a registry on behalf
   of the user."*
3. `jobs-front/.cursor/skills/job-scout-ui/SKILL.md` and the JE-006 and JE-009
   specs direct agents to search React Bits, Magic UI, 21st.dev and
   Aceternity/Cult UI.

Agents were told to source from registries, given none, and forbidden from
guessing. The sourcing policy existed only in prose. Restating the policy
without configuring the tooling would reproduce the same result.

## Registry configuration

`components.json` gains a populated `registries` map. Four namespaces are
present in the official shadcn registry index at
`https://ui.shadcn.com/r/registries.json` and are resolvable by the CLI:

| Namespace | URL template |
| --- | --- |
| `@magicui` | `https://magicui.design/r/{name}` |
| `@aceternity` | `https://ui.aceternity.com/registry/{name}.json` |
| `@cult-ui` | `https://cult-ui.com/r/{name}.json` |
| `@kokonutui` | `https://kokonutui.com/r/{name}.json` |

React Bits is **not** in the official index and has no MCP server. It requires an
explicit entry:

| Namespace | URL template |
| --- | --- |
| `@reactbits` | `https://reactbits.dev/r/{name}.json` |

Constraints the configuration must respect:

- Namespace names begin with `@`; URLs contain the `{name}` placeholder.
- `@shadcn` is built in and is not added to the map.
- A gated registry uses the object form with `headers` and a `${VAR}` reference
  resolved from the environment. No key, token, or secret is written into any
  tracked file.
- Public GitHub registries need no entry at all; `owner/repo/item[#ref]` is used
  directly when the repository exposes a root `registry.json`.

## MCP access

`jobs-front/.mcp.json` is added so Claude Code reaches the same servers Cursor
already has configured in the user's global `~/.cursor/mcp.json`: `shadcn`,
`playwright`, `magic-ui`, and `21st-dev`. The file is tracked. The workspace root
is not a git repository, so the tracked copy lives in `jobs-front/`.

The `21st-dev` server authenticates with `TWENTY_FIRST_API_KEY`, read from the
environment. That variable is **not currently set anywhere** on this machine, so
21st.dev is unavailable to Cursor today despite being configured. Consequences:

- The key requirement is documented in `jobs-front/.env.example` with no value.
- Absence of the key is a degraded state, not a failure. Tooling that cannot
  reach 21st.dev reports it as unavailable and continues with the remaining
  registries. Nothing in the batch may block on it.
- The key is never committed.

React Bits and Aceternity have no MCP server. They are reachable only through the
shadcn CLI and the shadcn MCP once the namespaces above are configured. Any
instruction implying an MCP for them is incorrect.

## Component source ledger

The task's central artifact is a ledger committed to
`jobs-front/docs/design/component-source-ledger.md`. It maps every UI need
identified in Batch 05 to a concrete, verified source.

Each row records:

- the UI need, in product terms (job card, banner, empty state, theme toggle,
  ambient background, tag input, pagination, and so on);
- the chosen registry item, written as the exact add target
  (`@namespace/item-name`, or `owner/repo/item`);
- the exact install command;
- the license of the source;
- dependencies the item pulls in;
- whether the item is Base UI or Radix based;
- a one-line reason the item was chosen over the alternatives considered.

Ledger rules:

- Every row is **verified to exist** by querying the registries through the
  shadcn MCP (`search_items_in_registries`, `view_items_in_registries`) or, for
  React Bits, by resolving the item URL directly. An unverified row is not a row.
- React Bits publishes item variants across JavaScript/TypeScript and
  CSS/Tailwind axes, so item names carry suffixes. The ledger records the exact
  variant name matching this project — TypeScript and Tailwind — never a guessed
  base name.
- Where the existing `@shadcn` registry already satisfies a need, the ledger says
  so and names it. Premium sourcing is not a reason to displace a shadcn
  primitive that fits.
- Where no registry item fits and custom code is warranted, the ledger records
  that decision and its justification. The absence of a suitable component is a
  legitimate finding, not a gap to be filled by inventing a row.
- A component whose license does not permit use in this project is not listed.

## Sourcing instructions

`jobs-front/.cursor/skills/job-scout-ui/SKILL.md` is updated so its sourcing rule
names the configured registries and points at the ledger as the resolved answer,
rather than naming registries an agent has no way to reach. The updated rule
directs agents to consult the ledger first, and to extend it — with verification
— when a genuinely new need arises.

The JE-006 and JE-009 specs are historical and are not rewritten.

## Out of scope

- Installing any component. JE-018 consumes the ledger and installs.
- Any change to `src/`, to design tokens, or to rendered output.
- Any visual or layout change.
- Obtaining or storing the 21st.dev API key. That is a user action.
- Adding registries beyond those named above.

## Acceptance criteria

1. `components.json` contains a `registries` map with `@magicui`, `@aceternity`,
   `@cult-ui`, `@kokonutui`, and `@reactbits`, each with a `{name}` placeholder,
   and `@shadcn` is not redeclared.
2. `jobs-front/.mcp.json` exists, is tracked, and configures the `shadcn`,
   `playwright`, `magic-ui`, and `21st-dev` servers.
3. No API key, token, or secret appears in any tracked file. The 21st.dev key is
   referenced as an environment variable and documented in `.env.example`
   without a value.
4. With `TWENTY_FIRST_API_KEY` unset, registry resolution for every other
   namespace still succeeds, and the unavailability of 21st.dev is reported
   rather than raised as a failure.
5. `jobs-front/docs/design/component-source-ledger.md` exists and covers every UI
   need enumerated in the JE-018 through JE-021 specs.
6. Every ledger row names an item verified to exist, with its exact add target,
   install command, license, dependencies, and Base UI/Radix provenance.
7. React Bits rows name the exact TypeScript + Tailwind variant item name.
8. Rows that resolve to `@shadcn` or to custom code are recorded as such with a
   stated reason.
9. `job-scout-ui/SKILL.md` names only configured registries and directs agents to
   the ledger.
10. No file under `jobs-front/src/` is modified, and rendered output is unchanged.
