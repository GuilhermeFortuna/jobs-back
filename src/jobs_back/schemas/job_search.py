"""Request and response schemas for the job search API."""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from fastapi import Query
from fastapi.exceptions import RequestValidationError
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)
from pydantic_core import InitErrorDetails

from jobs_back.models.enums import EmploymentType, RemoteType
from jobs_back.schemas.job import JobSummary

_ISO_ALPHA2_RE = re.compile(r"^[A-Z]{2}$")
_ISO_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")
_PROVIDER_KEY_RE = re.compile(r"^[a-z0-9_-]+$")


class JobSort(StrEnum):
    NEWEST = "newest"
    SALARY_ASC = "salary_asc"
    SALARY_DESC = "salary_desc"


class JobPage(BaseModel):
    """Paginated list of job summaries."""

    items: list[JobSummary]
    page: int
    page_size: int
    total: int
    total_pages: int


class JobSearchParams(BaseModel):
    """Validated query parameters for GET /jobs."""

    model_config = ConfigDict(extra="forbid")

    q: str | None = None
    location: str | None = None
    remote_type: list[RemoteType] = Field(default_factory=list)
    eligible_country: list[str] = Field(default_factory=list)
    employment_type: list[EmploymentType] = Field(default_factory=list)
    provider: list[str] = Field(default_factory=list)
    posted_after: datetime | None = None
    sort: JobSort = JobSort.NEWEST
    salary_min: Decimal | None = None
    salary_max: Decimal | None = None
    salary_currency: str | None = None
    page: int = 1
    page_size: int = 20

    @field_validator("q", "location", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: object) -> str | None:
        if value is None or value == "":
            return None
        if not isinstance(value, str):
            raise ValueError("must be a string")
        cleaned = value.strip()
        if not cleaned:
            return None
        if len(cleaned) > 200:
            raise ValueError("must be at most 200 characters")
        return cleaned

    @field_validator("remote_type", mode="before")
    @classmethod
    def dedupe_remote_types(cls, value: object) -> list[RemoteType]:
        return _dedupe_enum_list(value, RemoteType, "remote_type")

    @field_validator("employment_type", mode="before")
    @classmethod
    def dedupe_employment_types(cls, value: object) -> list[EmploymentType]:
        return _dedupe_enum_list(value, EmploymentType, "employment_type")

    @field_validator("provider", mode="before")
    @classmethod
    def normalize_providers(cls, value: object) -> list[str]:
        if value is None:
            return []
        items = value if isinstance(value, list) else [value]
        normalized: list[str] = []
        seen: set[str] = set()
        for item in items:
            if not isinstance(item, str):
                raise ValueError("provider values must be strings")
            cleaned = item.strip()
            if not cleaned or not _PROVIDER_KEY_RE.fullmatch(cleaned):
                raise ValueError(
                    "provider must be a lowercase key of letters, digits, _, or -"
                )
            if cleaned not in seen:
                seen.add(cleaned)
                normalized.append(cleaned)
        return normalized

    @field_validator("eligible_country", mode="before")
    @classmethod
    def normalize_eligible_countries(cls, value: object) -> list[str]:
        if value is None:
            return []
        items = value if isinstance(value, list) else [value]
        normalized: list[str] = []
        seen: set[str] = set()
        for item in items:
            if not isinstance(item, str):
                raise ValueError("eligible_country values must be strings")
            code = item.strip().upper()
            if not _ISO_ALPHA2_RE.fullmatch(code):
                raise ValueError(
                    "eligible_country must be an uppercase ISO 3166-1 alpha-2 code"
                )
            if code not in seen:
                seen.add(code)
                normalized.append(code)
        return normalized

    @field_validator("posted_after", mode="before")
    @classmethod
    def parse_posted_after(cls, value: object) -> datetime | None:
        if value is None or value == "":
            return None
        if isinstance(value, datetime):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("posted_after must be timezone-aware")
            return value
        if not isinstance(value, str):
            raise ValueError("posted_after must be an RFC 3339 timestamp")
        normalized = value.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise ValueError("posted_after must be an RFC 3339 timestamp") from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("posted_after must be timezone-aware")
        return parsed

    @field_validator("salary_min", "salary_max", mode="before")
    @classmethod
    def validate_salary_bound(cls, value: object) -> Decimal | None:
        if value is None or value == "":
            return None
        try:
            amount = value if isinstance(value, Decimal) else Decimal(str(value))
        except Exception as exc:
            raise ValueError("must be a non-negative decimal") from exc
        if not amount.is_finite() or amount < 0:
            raise ValueError("must be a non-negative decimal")
        return amount

    @field_validator("salary_currency", mode="before")
    @classmethod
    def normalize_salary_currency(cls, value: object) -> str | None:
        if value is None or value == "":
            return None
        if not isinstance(value, str):
            raise ValueError("salary_currency must be a string")
        code = value.strip().upper()
        if not _ISO_CURRENCY_RE.fullmatch(code):
            raise ValueError("salary_currency must be an uppercase ISO 4217 code")
        return code

    @field_validator("page")
    @classmethod
    def validate_page(cls, value: int) -> int:
        if value < 1:
            raise ValueError("page must be >= 1")
        return value

    @field_validator("page_size")
    @classmethod
    def validate_page_size(cls, value: int) -> int:
        if value < 1 or value > 100:
            raise ValueError("page_size must be between 1 and 100")
        return value

    @model_validator(mode="after")
    def validate_salary_requirements(self) -> JobSearchParams:
        if (
            self.salary_min is not None
            and self.salary_max is not None
            and self.salary_min > self.salary_max
        ):
            raise ValueError("salary_min must be <= salary_max")

        needs_currency = (
            self.salary_min is not None
            or self.salary_max is not None
            or self.sort in (JobSort.SALARY_ASC, JobSort.SALARY_DESC)
        )
        if needs_currency and self.salary_currency is None:
            raise ValidationError.from_exception_data(
                "JobSearchParams",
                [
                    InitErrorDetails(
                        type="missing",
                        loc=("salary_currency",),
                        input=self.salary_currency,
                        ctx={
                            "error": ValueError(
                                "salary_currency is required when filtering "
                                "or sorting by salary"
                            )
                        },
                    )
                ],
            )
        return self


def _dedupe_enum_list[T: StrEnum](
    value: object,
    enum_cls: type[T],
    field_name: str,
) -> list[T]:
    if value is None:
        return []
    items = value if isinstance(value, list) else [value]
    normalized: list[T] = []
    seen: set[T] = set()
    for item in items:
        try:
            enum_value = item if isinstance(item, enum_cls) else enum_cls(item)
        except ValueError as exc:
            raise ValueError(f"invalid {field_name} value: {item!r}") from exc
        if enum_value not in seen:
            seen.add(enum_value)
            normalized.append(enum_value)
    return normalized


def job_search_params(
    q: Annotated[str | None, Query(max_length=200)] = None,
    location: Annotated[str | None, Query(max_length=200)] = None,
    remote_type: Annotated[list[RemoteType] | None, Query()] = None,
    eligible_country: Annotated[list[str] | None, Query()] = None,
    employment_type: Annotated[list[EmploymentType] | None, Query()] = None,
    provider: Annotated[list[str] | None, Query()] = None,
    posted_after: Annotated[str | None, Query()] = None,
    salary_min: Annotated[Decimal | None, Query()] = None,
    salary_max: Annotated[Decimal | None, Query()] = None,
    salary_currency: Annotated[str | None, Query()] = None,
    sort: JobSort = JobSort.NEWEST,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> JobSearchParams:
    """FastAPI dependency that parses and validates job search query parameters."""
    try:
        return JobSearchParams(
            q=q,
            location=location,
            remote_type=remote_type or [],
            eligible_country=eligible_country or [],
            employment_type=employment_type or [],
            provider=provider or [],
            posted_after=posted_after,
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency=salary_currency,
            sort=sort,
            page=page,
            page_size=page_size,
        )
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc
