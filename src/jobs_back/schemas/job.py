"""Pydantic types for normalized job input and public API responses."""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    HttpUrl,
    ValidationInfo,
    field_validator,
    model_validator,
)

from jobs_back.models.enums import (
    EmploymentType,
    JobStatus,
    RemoteType,
    SalaryPeriod,
)
from jobs_back.normalization.compensation import annualize_bounds, quantize_money

_PROVIDER_KEY_RE = re.compile(r"^[a-z0-9_-]+$")
_ISO_ALPHA2_RE = re.compile(r"^[A-Z]{2}$")
_ISO_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")


def _require_nonempty_str(value: str, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    cleaned = " ".join(value.split())
    if not cleaned:
        raise ValueError(f"{field_name} must be non-empty after trimming")
    return cleaned


def _parse_positive_money(value: Any, field_name: str) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise ValueError(f"{field_name} must be a positive decimal amount")
    try:
        amount = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"{field_name} must be a positive decimal amount") from exc
    if not amount.is_finite() or amount <= 0:
        raise ValueError(f"{field_name} must be a positive decimal amount")
    return quantize_money(amount)


def _require_aware(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value


class NormalizedJobInput(BaseModel):
    """Validated provider-neutral job input for ingestion (not an ORM object)."""

    model_config = ConfigDict(extra="forbid")

    provider: str
    provider_job_id: str
    raw_payload: dict[str, Any]
    title: str
    company: str
    description: str | None = None
    employment_type: EmploymentType = EmploymentType.UNSPECIFIED
    remote_type: RemoteType = RemoteType.UNSPECIFIED
    location_text: str | None = None
    city: str | None = None
    region: str | None = None
    country_code: str | None = None
    eligible_country_codes: list[str] | None = None
    salary_min: Decimal | None = None
    salary_max: Decimal | None = None
    salary_currency: str | None = None
    salary_period: SalaryPeriod | None = None
    salary_min_annual: Decimal | None = None
    salary_max_annual: Decimal | None = None
    job_url: HttpUrl
    apply_url: HttpUrl | None = None
    posted_at: datetime | None = None

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned or not _PROVIDER_KEY_RE.fullmatch(cleaned):
            raise ValueError(
                "provider must be a non-empty lowercase key of letters, digits, _, or -"
            )
        return cleaned

    @field_validator("provider_job_id", "title", "company")
    @classmethod
    def validate_required_text(cls, value: str, info: ValidationInfo) -> str:
        return _require_nonempty_str(value, info.field_name)

    @field_validator("description", "location_text", "city", "region", mode="before")
    @classmethod
    def empty_optional_text_to_none(cls, value: Any) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("must be a string or null")
        cleaned = " ".join(value.split())
        return cleaned or None

    @field_validator("country_code", mode="before")
    @classmethod
    def normalize_country_code(cls, value: Any) -> str | None:
        if value is None or value == "":
            return None
        if not isinstance(value, str):
            raise ValueError("country_code must be a string or null")
        code = value.strip().upper()
        if not _ISO_ALPHA2_RE.fullmatch(code):
            raise ValueError(
                "country_code must be an uppercase ISO 3166-1 alpha-2 code"
            )
        return code

    @field_validator("eligible_country_codes", mode="before")
    @classmethod
    def normalize_eligible_countries(cls, value: Any) -> list[str] | None:
        if value is None:
            return None
        if not isinstance(value, list):
            raise ValueError("eligible_country_codes must be a list or null")
        normalized: list[str] = []
        seen: set[str] = set()
        for item in value:
            if not isinstance(item, str):
                raise ValueError("eligible_country_codes values must be strings")
            code = item.strip().upper()
            if not _ISO_ALPHA2_RE.fullmatch(code):
                raise ValueError(
                    "eligible_country_codes must contain uppercase "
                    "ISO 3166-1 alpha-2 codes"
                )
            if code not in seen:
                seen.add(code)
                normalized.append(code)
        return sorted(normalized)

    @field_validator("salary_min", "salary_max", mode="before")
    @classmethod
    def validate_salary_amount(cls, value: Any, info: ValidationInfo) -> Decimal | None:
        if value is None:
            return None
        return _parse_positive_money(value, info.field_name)

    @field_validator("salary_currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: Any) -> str | None:
        if value is None or value == "":
            return None
        if not isinstance(value, str):
            raise ValueError("salary_currency must be a string or null")
        code = value.strip().upper()
        if not _ISO_CURRENCY_RE.fullmatch(code):
            raise ValueError("salary_currency must be an uppercase ISO 4217 code")
        return code

    @field_validator("posted_at")
    @classmethod
    def validate_posted_at(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return _require_aware(value, "posted_at")

    @model_validator(mode="after")
    def validate_compensation_and_annualize(self) -> NormalizedJobInput:
        has_amount = self.salary_min is not None or self.salary_max is not None
        if has_amount:
            if self.salary_currency is None:
                raise ValueError(
                    "salary_currency is required when a salary amount is set"
                )
            if self.salary_period is None:
                raise ValueError(
                    "salary_period is required when a salary amount is set"
                )
        if (
            self.salary_min is not None
            and self.salary_max is not None
            and self.salary_min > self.salary_max
        ):
            raise ValueError("salary_min must be <= salary_max")

        annual_min, annual_max = annualize_bounds(
            self.salary_min,
            self.salary_max,
            self.salary_period,
        )
        self.salary_min_annual = annual_min
        self.salary_max_annual = annual_max
        return self


class JobSummary(BaseModel):
    """Public list-item representation of a job (never includes raw_payload)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: JobStatus
    provider: str
    provider_job_id: str
    title: str
    company: str
    location_text: str | None = None
    city: str | None = None
    region: str | None = None
    country_code: str | None = None
    eligible_country_codes: list[str] | None = None
    remote_type: RemoteType
    employment_type: EmploymentType
    salary_min: Decimal | None = None
    salary_max: Decimal | None = None
    salary_currency: str | None = None
    salary_period: SalaryPeriod | None = None
    salary_min_annual: Decimal | None = None
    salary_max_annual: Decimal | None = None
    job_url: str
    apply_url: str | None = None
    posted_at: datetime | None = None
    discovered_at: datetime
    last_seen_at: datetime


class JobDetail(JobSummary):
    """Public detail representation; adds description and lifecycle timestamps."""

    description: str | None = None
    updated_at: datetime
    inactive_at: datetime | None = None
