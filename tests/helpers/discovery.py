"""Shared helpers for JE-004 discovery/library tests."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from jobs_back.schemas.discovery import JobResult


def make_job_result(**overrides: object) -> JobResult:
    data: dict[str, object] = {
        "provider": "himalayas",
        "provider_job_id": "stable-provider-id",
        "title": "Senior Python Developer",
        "company": "Acme Corp",
        "description": "Build distributed systems",
        "location_text": "Remote - US",
        "eligible_country_codes": ["US"],
        "employment_type": "full_time",
        "remote_type": "remote",
        "seniority": "senior",
        "salary_min_annual": Decimal("120000"),
        "salary_max_annual": Decimal("160000"),
        "salary_currency": "USD",
        "job_url": "https://example.com/jobs/1",
        "apply_url": "https://example.com/jobs/1/apply",
        "company_logo_url": "https://example.com/logo.png",
        "posted_at": datetime(2026, 1, 15, tzinfo=UTC),
        "provider_payload": {"guid": "https://example.com/jobs/1", "internal": True},
    }
    data.update(overrides)
    return JobResult.model_validate(data)
