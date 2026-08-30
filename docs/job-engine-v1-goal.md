# Job Engine V1 Goal

## Objective

Build a centralized web application for discovering and browsing job openings aggregated from multiple external providers.

V1 is focused entirely on **job discovery, normalization, search, filtering, and presentation**.

## Core V1 Scope

- Integrate multiple job data providers behind a common provider interface.
- Fetch and normalize job postings into a shared internal schema.
- Store normalized jobs in a central database.
- Expose a unified search API across all integrated providers.
- Provide a web UI for searching and browsing jobs from all sources.
- Support deterministic filtering and sorting.
- Detect and consolidate duplicate listings where possible.
- Preserve the original source and application URL for every job.

## Search and Filtering

The UI should support, at minimum:

- Keyword search
- Location
- Remote / hybrid / on-site
- Country or region eligibility
- Employment type
- Salary range
- Provider/source
- Posting date
- Sort by newest
- Sort by salary

## Normalized Job Model

The internal representation should include fields such as:

```text
id
provider
provider_job_id
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
discovered_at
```

The provider-specific implementation should remain isolated from the rest of the application.

```text
External Providers
        ↓
Provider Adapters
        ↓
Normalization
        ↓
Central Database
        ↓
Search / Filter API
        ↓
Web UI
```

## Provider Strategy

V1 should prioritize providers that offer:

- Broad job coverage
- Free access or a generous renewable free tier
- Reliable structured APIs, feeds, or similarly practical access
- Good pagination or bulk retrieval
- Fresh listings
- Useful location and remote-work metadata
- Clear application URLs
- Terms compatible with displaying aggregated job listings

Provider selection should optimize for **maximum useful non-overlapping coverage**, rather than simply maximizing the number of integrations.

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

These features can be added after the job aggregation and search foundation is stable.

## V1 Success Criteria

V1 is successful when a user can open one application, search across all integrated sources, apply useful filters, compare results, and reach the original application page without needing to search each provider individually.
