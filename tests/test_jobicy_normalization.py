from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

from jobs_back.providers.jobicy import RESULT_CAP, normalize_job

FIXTURES = Path(__file__).parent / "fixtures" / "jobicy"


@pytest.fixture
def sample_payload() -> dict:
    return json.loads((FIXTURES / "sample.json").read_text())


def test_normalizes_identity(sample_payload: dict) -> None:
    job = normalize_job(sample_payload["jobs"][0])
    assert job is not None
    assert job.provider == "jobicy"
    assert job.provider_job_id == "152312"
    assert job.title == "Product Data Analyst"
    assert job.company == "Binance"


def test_normalizes_compensation(sample_payload: dict) -> None:
    job = normalize_job(sample_payload["jobs"][0])
    assert job is not None
    assert job.salary_min_annual == Decimal("80000")
    assert job.salary_max_annual == Decimal("120000")
    assert job.salary_currency == "USD"


def test_normalizes_timestamp(sample_payload: dict) -> None:
    job = normalize_job(sample_payload["jobs"][0])
    assert job is not None
    assert job.posted_at == datetime.fromisoformat("2026-09-01T12:01:55+00:00")


def test_result_cap_constant_documents_observed_limit() -> None:
    assert RESULT_CAP == 50
