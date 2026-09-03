# ADR-001 — Persist Personal Intent, Search Providers Live

## Status

Accepted for Batch 02 on 2026-09-01. Supersedes the Batch 01 runtime architecture
without invalidating Batch 01's completed historical deliverables.

## Context

Batch 01 built a normalized PostgreSQL provider catalog, ingestion service, and
database search API. Job Scout is not intended to be a general public job
platform. It is a personal/trusted-network tool where each person cares about a
narrow search and the jobs they intentionally retain.

Persisting every provider listing consumes storage, requires catalog lifecycle
operations, and makes database search serve a product need that no longer
exists. Persisting every listing a user happened to search is also incorrect:
viewing a transient result is not durable user intent.

## Decision

1. PostgreSQL persists trusted profiles, default search preferences, and job
   snapshots explicitly in `saved` or `applied` state.
2. Provider catalogs, ordinary searches, result pages, and warm indexes are not
   persisted.
3. Searches execute live through provider adapters. A single backend process
   maintains bounded, per-profile progressive indexes in memory.
4. Partial results and progress are visible during loading. Totals and final
   sorting become exact only at completion. Compatible stale results remain
   usable during refresh.
5. Himalayas is the first provider. Supported filters are pushed upstream; the
   backend fetches the complete matching set and applies remaining filters and
   final sort locally.
6. Profiles have no authentication in V1 but remain completely isolated by
   explicit `profile_id` scoping.
7. Saving resolves an authoritative in-memory result on the backend and writes
   a durable snapshot that survives provider removal and cache eviction.

## Consequences

Benefits:

- Durable storage matches deliberate personal actions.
- Live results are fresh without maintaining a duplicate catalog.
- Provider-specific behavior remains isolated.
- Each profile gets its own defaults and library without production account
  infrastructure.

Costs and constraints:

- Search results disappear after cache eviction or restart unless saved.
- Startup warming and stale refresh require explicit lifecycle management.
- V1 must run one backend process; multiple workers would not share search IDs.
- Exact totals and final order are delayed until the matching set is loaded.
- Provider availability and rate limits become visible product concerns.

## Rejected alternatives

- Persist the entire provider catalog: excessive for the personal product and
  reintroduces ingestion/lifecycle work.
- Persist every searched result: treats incidental viewing as user intent and
  still accumulates unwanted jobs.
- Browser-only provider fetching: exposes provider details, weakens normalization
  consistency, and prevents authoritative snapshots.
- Distributed cache in Batch 02: unnecessary complexity before a single-process
  personal deployment is proven insufficient.

