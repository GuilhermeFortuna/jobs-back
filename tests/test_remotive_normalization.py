from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from jobs_back.providers.remotive import (
    ATTRIBUTION_URL,
    RESULT_CAP,
    normalize_job,
    parse_free_text_salary,
)

FIXTURES = Path(__file__).parent / "fixtures" / "remotive"


@pytest.fixture
def sample_payload() -> dict:
    return json.loads((FIXTURES / "sample.json").read_text())


def test_normalizes_identity(sample_payload: dict) -> None:
    job = normalize_job(sample_payload["jobs"][0])
    assert job is not None
    assert job.provider == "remotive"
    assert job.provider_job_id == "2091101"
    assert job.title == "Senior React Full-stack Developer"
    assert job.company == "Lemon.io"
    assert str(job.job_url) == (
        "https://remotive.com/remote-jobs/software-development/"
        "senior-react-full-stack-developer-2091101"
    )
    assert job.employment_type == "full_time"
    assert job.location_text == "LATAM, Europe, USA"
    assert job.seniority == "react, javascript, node.js"


def test_normalizes_compensation(sample_payload: dict) -> None:
    first = normalize_job(sample_payload["jobs"][0])
    second = normalize_job(sample_payload["jobs"][1])
    assert first is not None
    assert second is not None
    assert first.salary_min_annual == Decimal("120000")
    assert first.salary_max_annual == Decimal("160000")
    assert first.salary_currency == "USD"
    assert second.salary_min_annual == Decimal("80000")
    assert second.salary_max_annual is None
    assert second.salary_currency == "EUR"


def test_normalizes_timestamp(sample_payload: dict) -> None:
    job = normalize_job(sample_payload["jobs"][0])
    assert job is not None
    assert job.posted_at == datetime(2026, 8, 27, 14, 36, 9, tzinfo=UTC)


def test_result_cap_constant_documents_observed_limit() -> None:
    assert RESULT_CAP == 50


def test_preserves_attribution_in_payload(sample_payload: dict) -> None:
    job = normalize_job(sample_payload["jobs"][0])
    assert job is not None
    assert job.provider_payload["attribution_url"] == ATTRIBUTION_URL
    assert "Remotive" in job.provider_payload["attribution_text"]


@pytest.mark.parametrize(
    ("salary_text", "salary_min", "salary_max", "currency"),
    [
        ("$120k - $160k", Decimal("120000"), Decimal("160000"), "USD"),
        ("€80,000/year", Decimal("80000"), None, "EUR"),
        ("$100k", Decimal("100000"), None, "USD"),
        ("competitive", None, None, None),
        ("DOE", None, None, None),
        ("120", None, None, None),
        ("100k", None, None, None),
    ],
)
def test_parse_free_text_salary_table(
    salary_text: str,
    salary_min: Decimal | None,
    salary_max: Decimal | None,
    currency: str | None,
) -> None:
    parsed_min, parsed_max, parsed_currency = parse_free_text_salary(salary_text)
    assert parsed_min == salary_min
    assert parsed_max == salary_max
    assert parsed_currency == currency
