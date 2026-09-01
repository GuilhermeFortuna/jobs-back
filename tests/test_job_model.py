"""PostgreSQL integration tests for the Job model and constraints."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from jobs_back.models import Job
from jobs_back.models.enums import JobStatus, SalaryPeriod
from tests.helpers.jobs import make_job as _job


def test_round_trip_minimal_job(db_session: Session) -> None:
    job = _job()
    db_session.add(job)
    db_session.flush()
    loaded = db_session.get(Job, job.id)
    assert loaded is not None
    assert loaded.title == "Software Engineer"
    assert loaded.eligible_country_codes is None
    assert loaded.salary_min is None
    assert loaded.status == JobStatus.ACTIVE.value
    assert loaded.inactive_at is None


def test_round_trip_fully_populated_job(db_session: Session) -> None:
    now = datetime.now(tz=UTC)
    job = _job(
        description="Build APIs",
        location_text="Remote - US",
        city="Austin",
        region="TX",
        country_code="US",
        eligible_country_codes=["CA", "US"],
        salary_min=Decimal("100000.00"),
        salary_max=Decimal("140000.00"),
        salary_currency="USD",
        salary_period=SalaryPeriod.YEARLY.value,
        salary_min_annual=Decimal("100000.00"),
        salary_max_annual=Decimal("140000.00"),
        apply_url="https://example.com/apply/1",
        posted_at=now,
    )
    db_session.add(job)
    db_session.flush()
    loaded = db_session.get(Job, job.id)
    assert loaded is not None
    assert loaded.description == "Build APIs"
    assert loaded.eligible_country_codes == ["CA", "US"]
    assert loaded.salary_min == Decimal("100000.00")
    assert loaded.raw_payload == {"source": "test"}


def test_provider_identity_unique(db_session: Session) -> None:
    first = _job(provider="example", provider_job_id="same-id")
    second = _job(provider="example", provider_job_id="same-id")
    db_session.add(first)
    db_session.flush()
    db_session.add(second)
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_same_provider_job_id_different_providers_ok(db_session: Session) -> None:
    a = _job(provider="alpha", provider_job_id="shared")
    b = _job(provider="beta", provider_job_id="shared")
    db_session.add_all([a, b])
    db_session.flush()
    assert a.id != b.id


@pytest.mark.parametrize(
    "overrides",
    [
        {"title": "   "},
        {"company": ""},
        {"provider": " "},
        {"provider_job_id": ""},
        {"job_url": " "},
        {"salary_min": Decimal("0")},
        {"salary_min": Decimal("-1")},
        {
            "salary_min": Decimal("200000.00"),
            "salary_max": Decimal("100000.00"),
        },
        {"status": JobStatus.ACTIVE.value, "inactive_at": datetime.now(tz=UTC)},
        {"status": JobStatus.INACTIVE.value, "inactive_at": None},
    ],
)
def test_check_constraints_reject_invalid_rows(
    db_session: Session,
    overrides: dict[str, object],
) -> None:
    db_session.add(_job(**overrides))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_lifecycle_active_inactive_active_preserves_id_and_discovered_at(
    db_session: Session,
) -> None:
    job = _job()
    db_session.add(job)
    db_session.flush()
    original_id = job.id
    original_discovered = job.discovered_at

    job.status = JobStatus.INACTIVE.value
    job.inactive_at = datetime.now(tz=UTC)
    job.updated_at = datetime.now(tz=UTC)
    db_session.flush()

    job.status = JobStatus.ACTIVE.value
    job.inactive_at = None
    job.updated_at = datetime.now(tz=UTC)
    db_session.flush()

    loaded = db_session.get(Job, original_id)
    assert loaded is not None
    assert loaded.id == original_id
    assert loaded.discovered_at == original_discovered
    assert loaded.status == JobStatus.ACTIVE.value
    assert loaded.inactive_at is None


def test_eligibility_null_vs_empty_distinct(db_session: Session) -> None:
    unknown = _job(provider_job_id="unknown-elig", eligible_country_codes=None)
    worldwide = _job(provider_job_id="worldwide", eligible_country_codes=[])
    db_session.add_all([unknown, worldwide])
    db_session.flush()
    assert db_session.get(Job, unknown.id).eligible_country_codes is None  # type: ignore[union-attr]
    assert db_session.get(Job, worldwide.id).eligible_country_codes == []  # type: ignore[union-attr]
