from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from jobs_back.providers.remoteok import ATTRIBUTION_URL, normalize_job

FIXTURES = Path(__file__).parent / "fixtures" / "remoteok"


@pytest.fixture
def sample_payload() -> list[dict]:
    return json.loads((FIXTURES / "sample.json").read_text())


def test_skips_legal_notice_element(sample_payload: list[dict]) -> None:
    jobs = [normalize_job(item) for item in sample_payload]
    assert jobs[0] is None
    assert jobs[1] is not None


def test_normalizes_identity_and_urls(sample_payload: list[dict]) -> None:
    job = normalize_job(sample_payload[1])
    assert job is not None
    assert job.provider == "remoteok"
    assert job.provider_job_id == "12345"
    assert job.title == "Senior Python Developer"
    assert str(job.job_url) == "https://remoteok.com/remote-jobs/12345"
    assert str(job.apply_url) == "https://acme.example/apply"


def test_normalizes_compensation(sample_payload: list[dict]) -> None:
    job = normalize_job(sample_payload[1])
    assert job is not None
    assert job.salary_min_annual == Decimal("120000")
    assert job.salary_max_annual == Decimal("160000")
    assert job.salary_currency == "USD"


@pytest.mark.parametrize(
    ("epoch", "expected"),
    [
        (1700000000, datetime(2023, 11, 14, 22, 13, 20, tzinfo=UTC)),
        ("1700000000", datetime(2023, 11, 14, 22, 13, 20, tzinfo=UTC)),
    ],
)
def test_epoch_timestamp(epoch: object, expected: datetime) -> None:
    job = normalize_job(
        {
            "id": "1",
            "position": "Engineer",
            "company": "Co",
            "epoch": epoch,
            "url": "https://remoteok.com/1",
        }
    )
    assert job is not None
    assert job.posted_at == expected


def test_preserves_attribution_in_payload(sample_payload: list[dict]) -> None:
    job = normalize_job(sample_payload[1])
    assert job is not None
    assert job.provider_payload["attribution_url"] == ATTRIBUTION_URL
    assert "Remote OK" in job.provider_payload["attribution_text"]
