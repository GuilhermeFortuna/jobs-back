# JE-004 — Trusted Profiles and Personal Job Library Specification

## Status

In progress for Batch 02. This specification supersedes the user-specific state
that JE-003 deliberately deferred. It does not require authentication because
Job Scout is a personal or trusted-network application.

## Purpose

Persist only durable user intent: profiles, each profile's default search, and
job snapshots explicitly saved or marked as applied. Provider catalogs and
ordinary search results are not durable application data.

## Trusted profiles

A profile contains:

- UUID `id`;
- unique, trimmed `display_name` from 1 through 80 characters;
- one structured `preferences` object matching JE-005 search filters;
- `created_at` and `updated_at` timestamps.

Profiles are selected explicitly in the UI. There is no login, password,
session, ownership claim, or authorization layer in this batch. Every
profile-scoped endpoint nevertheless includes `profile_id`, and one profile
must never read, change, or delete another profile's library records or
preferences.

## Personal library

A library row is a provider snapshot chosen by one profile. Its state is exactly
one of:

- `saved` — worth revisiting;
- `applied` — the user has applied.

The snapshot preserves provider identity, normalized title/company/content,
location and eligibility, employment and remote type, seniority, annual salary
bounds and currency, source/application URLs, logo URL, posting timestamp, and
the accepted provider payload. It remains readable even when the live provider
no longer returns the listing.

Identity is unique on `(profile_id, provider, provider_job_id)`. Saving the same
result again is idempotent: it returns or updates the existing library row
instead of creating a duplicate.

State rules:

- entering `applied` sets `applied_at` if it is not already set;
- changing back to `saved` clears `applied_at`;
- repeated writes of the current state preserve meaningful timestamps;
- either state can be permanently deleted;
- deletion affects only the selected profile's snapshot.

## Endpoints

### Profiles

- `GET /profiles`
- `POST /profiles`
- `GET /profiles/{profile_id}`
- `PATCH /profiles/{profile_id}`

Creating a profile accepts `display_name` and optional default preferences.
Patching accepts either field. Duplicate names return `409`; unknown valid UUIDs
return `404`; malformed input returns `422`.

### Library

- `GET /profiles/{profile_id}/jobs?state=saved|applied`
- `POST /profiles/{profile_id}/jobs`
- `GET /profiles/{profile_id}/jobs/{job_id}`
- `PATCH /profiles/{profile_id}/jobs/{job_id}`
- `DELETE /profiles/{profile_id}/jobs/{job_id}`

The preferred save request identifies an in-memory JE-005 result:

```json
{
  "search_id": "uuid",
  "provider": "himalayas",
  "provider_job_id": "stable-provider-id",
  "state": "saved"
}
```

The backend resolves that identity from its search index and writes the complete
snapshot. This avoids trusting a client-supplied snapshot and preserves provider
payload data that is intentionally absent from public search responses. An
expired or mismatched search identity returns `410` or `404` without persisting
anything.

Library list order is deterministic: newest relevant state timestamp first,
then UUID. Responses never expose the raw provider payload.

## Database transition from Batch 01

The active schema after this batch stores profiles and library snapshots, not a
provider catalog. The forward migration must inspect legacy `jobs` and
`sync_runs` before removing them. If either contains user-relevant data, the
migration stops with an actionable error instead of silently discarding rows.
Empty legacy catalog tables may be removed. Upgrade and downgrade behavior must
be tested against PostgreSQL.

Batch 01 remains accepted history: its documents and Git history are not
rewritten merely because its persistence architecture is superseded.

## Out of scope

- Authentication, invitations, roles, or access control
- Sharing jobs or preferences between profiles
- Notes, reminders, contacts, interview stages, or application automation
- Persisting searches, result pages, provider catalogs, or cache metadata
- Restoring deleted library rows

## Acceptance criteria

1. Profiles can be listed, created, read, and updated with validated unique
   names and structured preferences.
2. Preferences and library records remain completely isolated between profiles.
3. A live result can be saved as a complete durable snapshot and remains
   available independently of the live search cache.
4. Repeated saves do not duplicate `(profile, provider, provider_job_id)`.
5. Saved/applied transitions enforce the `applied_at` rules.
6. Either state can be permanently deleted without affecting another profile.
7. Public responses never expose accepted provider payloads.
8. The migration never silently discards a nonempty Batch 01 catalog.

