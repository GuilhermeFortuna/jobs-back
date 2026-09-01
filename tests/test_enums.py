"""Unit tests for domain string enums."""

from jobs_back.models.enums import (
    EmploymentType,
    JobStatus,
    RemoteType,
    SalaryPeriod,
)


def test_employment_type_values() -> None:
    assert {m.value for m in EmploymentType} == {
        "full_time",
        "part_time",
        "contract",
        "temporary",
        "internship",
        "other",
        "unspecified",
    }


def test_remote_type_values() -> None:
    assert {m.value for m in RemoteType} == {
        "remote",
        "hybrid",
        "on_site",
        "unspecified",
    }


def test_salary_period_values() -> None:
    assert {m.value for m in SalaryPeriod} == {
        "hourly",
        "daily",
        "weekly",
        "monthly",
        "yearly",
        "other",
    }


def test_job_status_values() -> None:
    assert {m.value for m in JobStatus} == {"active", "inactive"}


def test_enums_are_strings() -> None:
    assert EmploymentType.FULL_TIME == "full_time"
    assert RemoteType.ON_SITE == "on_site"
    assert SalaryPeriod.YEARLY == "yearly"
    assert JobStatus.ACTIVE == "active"
