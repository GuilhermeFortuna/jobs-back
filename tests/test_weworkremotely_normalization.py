from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from jobs_back.providers.weworkremotely import (
    ATTRIBUTION_URL,
    normalize_job,
    parse_feed,
    split_title_company,
)

FIXTURES = Path(__file__).parent / "fixtures" / "weworkremotely"


@pytest.fixture
def sample_feed() -> str:
    return (FIXTURES / "sample.rss").read_text()


@pytest.fixture
def sample_entries(sample_feed: str) -> list[dict]:
    return parse_feed(sample_feed)


@pytest.mark.parametrize(
    ("title", "company", "role"),
    [
        ("Acme Corp: Senior Engineer", "Acme Corp", "Senior Engineer"),
        ("No Separator Title", None, "No Separator Title"),
        ("A:B:C", "A", "B:C"),
        ("", None, None),
        (None, None, None),
    ],
)
def test_split_title_company_table(
    title: str | None,
    company: str | None,
    role: str | None,
) -> None:
    assert split_title_company(title) == (company, role)


def test_parse_feed_skips_malformed_entry(sample_entries: list[dict]) -> None:
    assert len(sample_entries) == 3


def test_normalizes_identity(sample_entries: list[dict]) -> None:
    job = normalize_job(sample_entries[0])
    assert job is not None
    assert job.provider == "weworkremotely"
    assert job.provider_job_id == (
        "https://weworkremotely.com/remote-jobs/acme-corp-senior-engineer"
    )
    assert job.title == "Senior Engineer"
    assert job.company == "Acme Corp"
    assert job.location_text == "Anywhere in the World, USA"
    assert job.employment_type == "full_time"
    assert job.seniority == "Python, Django"
    assert job.salary_min_annual is None
    assert job.salary_max_annual is None
    assert job.salary_currency is None


def test_no_separator_title_uses_unknown_company(sample_entries: list[dict]) -> None:
    job = normalize_job(sample_entries[1])
    assert job is not None
    assert job.title == "No Separator Title"
    assert job.company == "Unknown company"


def test_provider_job_id_stable_across_parses(sample_feed: str) -> None:
    first = [normalize_job(entry) for entry in parse_feed(sample_feed)]
    second = [normalize_job(entry) for entry in parse_feed(sample_feed)]
    first_ids = [job.provider_job_id for job in first if job is not None]
    second_ids = [job.provider_job_id for job in second if job is not None]
    assert first_ids == second_ids


def test_timestamp_normalization(sample_entries: list[dict]) -> None:
    job = normalize_job(sample_entries[0])
    assert job is not None
    assert job.posted_at == datetime(2026, 9, 1, 12, 0, tzinfo=UTC)


def test_preserves_attribution_in_payload(sample_entries: list[dict]) -> None:
    job = normalize_job(sample_entries[0])
    assert job is not None
    assert job.provider_payload["attribution_url"] == ATTRIBUTION_URL
    assert "We Work Remotely" in job.provider_payload["attribution_text"]
