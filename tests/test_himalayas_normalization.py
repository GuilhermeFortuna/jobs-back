from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from jobs_back.providers.himalayas import normalize_job
from jobs_back.providers.sanitize import strip_html


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (1700000000, datetime(2023, 11, 14, 22, 13, 20, tzinfo=UTC)),
        (1700000000000, datetime(2023, 11, 14, 22, 13, 20, tzinfo=UTC)),
        ("2024-01-15T10:00:00Z", datetime(2024, 1, 15, 10, 0, tzinfo=UTC)),
    ],
)
def test_timestamp_normalization(raw: object, expected: datetime) -> None:
    job = normalize_job({"guid": "job-1", "title": "Engineer", "pubDate": raw})
    assert job is not None
    assert job.posted_at == expected


@pytest.mark.parametrize(
    ("restrictions", "countries", "labels"),
    [
        (["United States"], [], ["United States"]),
        ([{"alpha2": "us", "name": "United States"}], ["US"], ["United States"]),
    ],
)
def test_location_restrictions(
    restrictions: list,
    countries: list[str],
    labels: list[str],
) -> None:
    job = normalize_job(
        {
            "guid": "job-1",
            "title": "Engineer",
            "locationRestrictions": restrictions,
        }
    )
    assert job is not None
    assert job.eligible_country_codes == countries or job.eligible_country_codes is None
    for label in labels:
        assert label in (job.location_text or "")


@pytest.mark.parametrize(
    ("period", "amount", "expected"),
    [
        ("hourly", 50, Decimal("104000")),
        ("weekly", 1000, Decimal("52000")),
        ("fortnightly", 2000, Decimal("52000")),
        ("monthly", 8000, Decimal("96000")),
        ("annual", 120000, Decimal("120000")),
    ],
)
def test_compensation_periods(period: str, amount: int, expected: Decimal) -> None:
    job = normalize_job(
        {
            "guid": "job-1",
            "title": "Engineer",
            "salaryPeriod": period,
            "minSalary": amount,
            "maxSalary": amount,
        }
    )
    assert job is not None
    assert job.salary_min_annual == expected
    assert job.salary_max_annual == expected


@pytest.mark.parametrize(
    ("employment", "expected"),
    [
        ("Full Time", "full_time"),
        ("Part Time", "part_time"),
        ("Contractor", "contract"),
        ("Temporary", "temporary"),
        ("Intern", "internship"),
        ("Volunteer", "other"),
        ("Other", "other"),
    ],
)
def test_employment_mapping(employment: str, expected: str) -> None:
    job = normalize_job(
        {"guid": "job-1", "title": "Engineer", "employmentType": employment}
    )
    assert job is not None
    assert job.employment_type == expected


def test_list_seniority_and_empty_logo() -> None:
    job = normalize_job(
        {
            "guid": "job-1",
            "title": "Engineer",
            "seniority": ["senior", "lead"],
            "companyLogo": "",
        }
    )
    assert job is not None
    assert job.seniority == "senior, lead"
    assert job.company_logo_url is None


def test_malformed_row_without_title_is_skipped() -> None:
    assert normalize_job({"guid": "job-1"}) is None


def test_description_html_is_stripped() -> None:
    job = normalize_job(
        {
            "guid": "job-1",
            "title": "Engineer",
            "descriptionHtml": "<p>Build <strong>systems</strong></p>",
        }
    )
    assert job is not None
    assert job.description == "Build systems"
    assert strip_html("<a href='x'>Link</a>") == "Link"
