# Job Scout V1 Goal

## Objective

Build a personal or trusted-network web application that searches external job
providers live and helps separate local profiles retain only the roles they save
or apply to.

V1 is focused on **personal job discovery, filtering, saved/applied tracking, and
durable user intent**.

## Core V1 Scope

- Support trusted profiles without authentication and keep their data separate.
- Store one default search preference set per profile.
- Search providers live behind a provider-neutral backend interface.
- Show useful partial results and progress while full matching results load.
- Keep warm search indexes in backend memory, with stale results during refresh.
- Persist only jobs explicitly saved or marked applied by a profile.
- Preserve saved snapshots after a provider removes a listing.
- Preserve the original source and application URL for every job.

## Search and Filtering

The UI should support, at minimum:

- Keyword search
- Location
- Worldwide or country eligibility
- Employment type
- Seniority
- Minimum annual salary
- Posting recency
- Sort by newest
- Sort by salary
- Sort by relevance

## Durable data model

PostgreSQL stores profile identity/preferences and selected job snapshots with
fields such as:

```text
profile_id
provider
provider_job_id
state: saved | applied
title
company
location
remote_type
employment_type
salary_min
salary_max
salary_currency
description
job_url
apply_url
posted_at
saved_at
applied_at
```

The provider-specific implementation should remain isolated from the rest of the application.

```text
External Providers
        ↓
Provider Adapters
        ↓
Normalization
        ↓
Per-profile in-memory search indexes
        ↓
Search / Filter API + user selection
        ↓
PostgreSQL personal library
        ↓
Web UI: Discover / Saved / Applied
```

## Provider Strategy

Himalayas is the first V1 provider. Later providers should prioritize:

- Broad job coverage
- Free access or a generous renewable free tier
- Reliable structured APIs, feeds, or similarly practical access
- Good pagination or bulk retrieval
- Fresh listings
- Useful location and remote-work metadata
- Clear application URLs

Provider selection should optimize for **maximum useful non-overlapping coverage**, rather than simply maximizing the number of integrations.

Component or dependency license analysis is not a project concern. Provider
access must still use available interfaces without bypassing credentials,
payments, or technical access controls, and source attribution requirements must
be preserved.

## Explicitly Out of Scope for V1

Do not include:

- Local AI models
- LLM-based job analysis
- Semantic search
- Resume matching
- AI-generated ranking
- Automated applications
- Agent workflows
- Application-form automation
- Authentication and public multi-tenant account infrastructure
- Persisted provider catalogs or every result a profile happens to view
- Distributed search caches or multiple backend workers
- Shared libraries and collaborative workflows

These features can be added after the job aggregation and search foundation is stable.

## V1 Success Criteria

V1 is successful when a person can select their profile, open a warmed useful
search, refine it while results load progressively, inspect and compare roles,
save or mark selected roles as applied, return to those durable snapshots later,
and reach the original application page without maintaining an unwanted local
copy of the provider catalog.
