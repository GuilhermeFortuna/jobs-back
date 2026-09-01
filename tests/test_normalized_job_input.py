"""Unit tests for NormalizedJobInput validation boundaries."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from jobs_back.models.enums import EmploymentType, RemoteType, SalaryPeriod
from jobs_back.schemas.job import NormalizedJobInput


def _base_kwargs(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "provider": "example",
        "provider_job_id": "job-1",
        "raw_payload": {"id": "job-1"},
        "title": "Software Engineer",
        "company": "Acme",
        "employment_type": EmploymentType.FULL_TIME,
        "remote_type": RemoteType.REMOTE,
        "job_url": "https://example.com/jobs/1",
    }
    data.update(overrides)
    return data


def test_minimal_valid_input() -> None:
    job = NormalizedJobInput.model_validate(_base_kwargs())
    assert job.provider == "example"
    assert job.salary_min_annual is None
    assert job.eligible_country_codes is None


def test_title_trimmed_whitespace() -> None:
    job = NormalizedJobInput.model_validate(_base_kwargs(title="  Senior  Dev  "))
    assert job.title == "Senior Dev"


@pytest.mark.parametrize(
    "field",
    ["provider", "provider_job_id", "title", "company"],
)
def test_required_strings_reject_blank(field: str) -> None:
    with pytest.raises(ValidationError):
        NormalizedJobInput.model_validate(_base_kwargs(**{field: "   "}))


@pytest.mark.parametrize(
    "provider",
    ["Bad Provider", "UPPER", "has space", "bad!", ""],
)
def test_provider_key_syntax(provider: str) -> None:
    with pytest.raises(ValidationError):
        NormalizedJobInput.model_validate(_base_kwargs(provider=provider))


def test_provider_key_allows_digits_underscore_hyphen() -> None:
    job = NormalizedJobInput.model_validate(
        _base_kwargs(provider="provider_1-test")
    )
    assert job.provider == "provider_1-test"


def test_country_code_normalized_and_validated() -> None:
    job = NormalizedJobInput.model_validate(_base_kwargs(country_code="us"))
    assert job.country_code == "US"
    with pytest.raises(ValidationError):
        NormalizedJobInput.model_validate(_base_kwargs(country_code="USA"))


def test_eligibility_null_empty_and_sorted_unique() -> None:
    unknown = NormalizedJobInput.model_validate(
        _base_kwargs(eligible_country_codes=None)
    )
    worldwide = NormalizedJobInput.model_validate(
        _base_kwargs(eligible_country_codes=[])
    )
    restricted = NormalizedJobInput.model_validate(
        _base_kwargs(eligible_country_codes=["br", "US", "us", "CA"])
    )
    assert unknown.eligible_country_codes is None
    assert worldwide.eligible_country_codes == []
    assert restricted.eligible_country_codes == ["BR", "CA", "US"]


def test_salary_requires_currency_and_period() -> None:
    with pytest.raises(ValidationError):
        NormalizedJobInput.model_validate(
            _base_kwargs(salary_min="100000", salary_period=SalaryPeriod.YEARLY)
        )
    with pytest.raises(ValidationError):
        NormalizedJobInput.model_validate(
            _base_kwargs(salary_min="100000", salary_currency="USD")
        )


def test_salary_annualization_yearly() -> None:
    job = NormalizedJobInput.model_validate(
        _base_kwargs(
            salary_min="100000",
            salary_max="120000",
            salary_currency="usd",
            salary_period=SalaryPeriod.YEARLY,
        )
    )
    assert job.salary_currency == "USD"
    assert job.salary_min == Decimal("100000.00")
    assert job.salary_min_annual == Decimal("100000.00")
    assert job.salary_max_annual == Decimal("120000.00")


def test_salary_other_not_annualized() -> None:
    job = NormalizedJobInput.model_validate(
        _base_kwargs(
            salary_min="50",
            salary_currency="USD",
            salary_period=SalaryPeriod.OTHER,
        )
    )
    assert job.salary_min == Decimal("50.00")
    assert job.salary_min_annual is None


@pytest.mark.parametrize(
    "salary_min",
    [0, -1, True, False, "not-a-number", float("nan"), float("inf")],
)
def test_salary_rejects_invalid_amounts(salary_min: object) -> None:
    with pytest.raises(ValidationError):
        NormalizedJobInput.model_validate(
            _base_kwargs(
                salary_min=salary_min,
                salary_currency="USD",
                salary_period=SalaryPeriod.YEARLY,
            )
        )


def test_salary_range_ordered() -> None:
    with pytest.raises(ValidationError):
        NormalizedJobInput.model_validate(
            _base_kwargs(
                salary_min="200000",
                salary_max="100000",
                salary_currency="USD",
                salary_period=SalaryPeriod.YEARLY,
            )
        )


def test_posted_at_must_be_timezone_aware() -> None:
    with pytest.raises(ValidationError):
        NormalizedJobInput.model_validate(
            _base_kwargs(posted_at=datetime(2024, 1, 1))
        )
    job = NormalizedJobInput.model_validate(
        _base_kwargs(posted_at=datetime(2024, 1, 1, tzinfo=UTC))
    )
    assert job.posted_at is not None


def test_job_url_required_shape() -> None:
    with pytest.raises(ValidationError):
        NormalizedJobInput.model_validate(_base_kwargs(job_url="not-a-url"))
