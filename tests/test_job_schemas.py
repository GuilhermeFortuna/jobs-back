"""Unit tests for public JobSummary / JobDetail schemas."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from jobs_back.models.enums import EmploymentType, JobStatus, RemoteType, SalaryPeriod
from jobs_back.schemas.job import JobDetail, JobSummary


def _summary_kwargs(**overrides: object) -> dict[str, object]:
    now = datetime(2024, 6, 1, tzinfo=UTC)
    data: dict[str, object] = {
        "id": uuid4(),
        "status": JobStatus.ACTIVE,
        "provider": "example",
        "provider_job_id": "job-1",
        "title": "Engineer",
        "company": "Acme",
        "remote_type": RemoteType.REMOTE,
        "employment_type": EmploymentType.FULL_TIME,
        "salary_min": Decimal("100000.00"),
        "salary_max": Decimal("120000.00"),
        "salary_currency": "USD",
        "salary_period": SalaryPeriod.YEARLY,
        "salary_min_annual": Decimal("100000.00"),
        "salary_max_annual": Decimal("120000.00"),
        "job_url": "https://example.com/jobs/1",
        "apply_url": None,
        "posted_at": now,
        "discovered_at": now,
        "last_seen_at": now,
        "eligible_country_codes": ["US"],
    }
    data.update(overrides)
    return data


def test_job_summary_excludes_raw_payload() -> None:
    summary = JobSummary.model_validate(_summary_kwargs())
    dumped = summary.model_dump()
    assert "raw_payload" not in dumped
    assert "description" not in dumped
    assert "updated_at" not in dumped
    assert "inactive_at" not in dumped


def test_job_detail_excludes_raw_payload_and_adds_fields() -> None:
    now = datetime(2024, 6, 1, tzinfo=UTC)
    detail = JobDetail.model_validate(
        {
            **_summary_kwargs(),
            "description": "Build things",
            "updated_at": now,
            "inactive_at": None,
        }
    )
    dumped = detail.model_dump()
    assert "raw_payload" not in dumped
    assert dumped["description"] == "Build things"
    assert dumped["updated_at"] == now
    assert dumped["inactive_at"] is None


def test_job_summary_rejects_raw_payload_field() -> None:
    """Extra fields are ignored by default; ensure dump still has no raw_payload."""
    summary = JobSummary.model_validate(
        {**_summary_kwargs(), "raw_payload": {"secret": True}}
    )
    assert "raw_payload" not in summary.model_dump()
    assert "raw_payload" not in JobSummary.model_fields
