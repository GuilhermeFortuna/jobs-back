"""Pure compensation annualization helpers (Decimal only)."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Final

from jobs_back.models.enums import SalaryPeriod

TWO_PLACES: Final = Decimal("0.01")

_ANNUAL_MULTIPLIERS: Final[dict[SalaryPeriod, Decimal]] = {
    SalaryPeriod.HOURLY: Decimal("2080"),
    SalaryPeriod.DAILY: Decimal("260"),
    SalaryPeriod.WEEKLY: Decimal("52"),
    SalaryPeriod.MONTHLY: Decimal("12"),
    SalaryPeriod.YEARLY: Decimal("1"),
}


def quantize_money(value: Decimal) -> Decimal:
    """Quantize a positive money amount to two decimal places."""
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def annualize_amount(
    amount: Decimal | None,
    period: SalaryPeriod | str | None,
) -> Decimal | None:
    """Convert a source amount to a comparable annual value.

    Returns None when amount or period is missing, or when period is ``other``
    (preserved at source but not annualized). Never guesses a missing period.
    """
    if amount is None or period is None:
        return None

    period_enum = period if isinstance(period, SalaryPeriod) else SalaryPeriod(period)
    if period_enum is SalaryPeriod.OTHER:
        return None

    multiplier = _ANNUAL_MULTIPLIERS[period_enum]
    return quantize_money(amount * multiplier)


def annualize_bounds(
    salary_min: Decimal | None,
    salary_max: Decimal | None,
    period: SalaryPeriod | str | None,
) -> tuple[Decimal | None, Decimal | None]:
    """Annualize min/max bounds independently with the same period rules."""
    return (
        annualize_amount(salary_min, period),
        annualize_amount(salary_max, period),
    )
