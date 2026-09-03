"""Unit tests for compensation annualization."""

from decimal import Decimal

import pytest

from jobs_back.models.enums import SalaryPeriod
from jobs_back.normalization.compensation import annualize_amount, annualize_bounds


@pytest.mark.parametrize(
    ("amount", "period", "expected"),
    [
        (Decimal("50.00"), SalaryPeriod.HOURLY, Decimal("104000.00")),
        (Decimal("400.00"), SalaryPeriod.DAILY, Decimal("104000.00")),
        (Decimal("2000.00"), SalaryPeriod.WEEKLY, Decimal("104000.00")),
        (Decimal("8666.67"), SalaryPeriod.MONTHLY, Decimal("104000.04")),
        (Decimal("104000.00"), SalaryPeriod.YEARLY, Decimal("104000.00")),
        (Decimal("104000.00"), SalaryPeriod.OTHER, None),
        (Decimal("104000.00"), None, None),
        (None, SalaryPeriod.YEARLY, None),
        (None, None, None),
    ],
)
def test_annualize_amount(
    amount: Decimal | None,
    period: SalaryPeriod | None,
    expected: Decimal | None,
) -> None:
    assert annualize_amount(amount, period) == expected


def test_annualize_amount_accepts_period_string() -> None:
    assert annualize_amount(Decimal("10"), "hourly") == Decimal("20800.00")


def test_annualize_bounds_one_sided() -> None:
    annual_min, annual_max = annualize_bounds(
        Decimal("100000"),
        None,
        SalaryPeriod.YEARLY,
    )
    assert annual_min == Decimal("100000.00")
    assert annual_max is None


def test_missing_period_not_guessed_for_large_value() -> None:
    assert annualize_amount(Decimal("120000"), None) is None
