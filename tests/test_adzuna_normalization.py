from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from jobs_back.providers.adzuna import (
    ATTRIBUTION_URL,
    normalize_job,
    resolve_country_code,
)

FIXTURES = Path(__file__).parent / "fixtures" / "adzuna"


@pytest.fixture
def sample_payload() -> dict:
    return json.loads((FIXTURES / "sample.json").read_text())


def test_normalizes_identity_and_urls(sample_payload: dict) -> None:
    job = normalize_job(sample_payload["results"][0], queried_country="gb")
    assert job is not None
    assert job.provider == "adzuna"
    assert job.provider_job_id == "129698749"
    assert job.title == "Senior Python Developer"
    assert job.company == "Acme Labs"
    assert str(job.job_url) == "https://www.adzuna.co.uk/jobs/land/ad/129698749"
    assert str(job.apply_url) == str(job.job_url)


def test_normalizes_compensation_and_currency(sample_payload: dict) -> None:
    job = normalize_job(sample_payload["results"][0], queried_country="gb")
    assert job is not None
    assert job.salary_min_annual == Decimal("80000")
    assert job.salary_max_annual == Decimal("120000")
    assert job.salary_currency == "GBP"


@pytest.mark.parametrize(
    ("contract_time", "contract_type", "expected"),
    [
        ("full_time", "permanent", "full_time"),
        ("part_time", "contract", "part_time"),
        ("", "contract", "contract"),
    ],
)
def test_contract_mapping(
    contract_time: str,
    contract_type: str,
    expected: str,
) -> None:
    job = normalize_job(
        {
            "id": "1",
            "title": "Engineer",
            "redirect_url": "https://www.adzuna.co.uk/jobs/1",
            "contract_time": contract_time,
            "contract_type": contract_type,
        },
        queried_country="gb",
    )
    assert job is not None
    assert job.employment_type == expected


def test_timestamp_normalization(sample_payload: dict) -> None:
    job = normalize_job(sample_payload["results"][0], queried_country="gb")
    assert job is not None
    assert job.posted_at == datetime(2024, 1, 15, 10, 0, tzinfo=UTC)


def test_preserves_attribution_and_queried_country(sample_payload: dict) -> None:
    job = normalize_job(sample_payload["results"][0], queried_country="gb")
    assert job is not None
    assert job.provider_payload["attribution_url"] == ATTRIBUTION_URL
    assert "Adzuna" in job.provider_payload["attribution_text"]
    assert job.provider_payload["queried_country"] == "gb"


@pytest.mark.parametrize(
    ("raw", "default", "expected"),
    [
        (None, "gb", "gb"),
        ("", "gb", "gb"),
        ("us", "gb", "us"),
        ("United States", "gb", "us"),
        ("United Kingdom", "gb", "gb"),
    ],
)
def test_resolve_country_code(raw: str | None, default: str, expected: str) -> None:
    assert resolve_country_code(raw, default) == expected
