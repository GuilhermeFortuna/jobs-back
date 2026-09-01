from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class SearchSort(StrEnum):
    RELEVANCE = "relevance"
    NEWEST = "newest"
    SALARY = "salary"


class SearchFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(default="", max_length=200)
    country: str | None = Field(default=None, max_length=80)
    worldwide: bool | None = None
    seniority: list[str] = Field(default_factory=list, max_length=10)
    employment_types: list[str] = Field(default_factory=list, max_length=10)
    minimum_salary: int | None = Field(default=None, ge=0, le=10_000_000)
    posted_within_days: int | None = Field(default=None, ge=1, le=3650)
    sort: SearchSort = SearchSort.RELEVANCE

    @field_validator("query")
    @classmethod
    def trim_query(cls, value: str) -> str:
        return " ".join(value.split())


class ProfileCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=80)
    preferences: SearchFilters = Field(default_factory=SearchFilters)


class ProfilePatch(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=80)
    preferences: SearchFilters | None = None


class ProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    display_name: str
    preferences: SearchFilters
    created_at: datetime
    updated_at: datetime


class JobResult(BaseModel):
    provider: str = "himalayas"
    provider_job_id: str
    title: str
    company: str
    description: str | None = None
    location_text: str | None = None
    eligible_country_codes: list[str] | None = None
    employment_type: str = "unspecified"
    remote_type: str = "remote"
    seniority: str | None = None
    salary_min_annual: Decimal | None = None
    salary_max_annual: Decimal | None = None
    salary_currency: str | None = None
    job_url: HttpUrl
    apply_url: HttpUrl | None = None
    company_logo_url: HttpUrl | None = None
    posted_at: datetime | None = None
    provider_payload: dict[str, Any] = Field(default_factory=dict, exclude=True)


class SavedJobCreate(BaseModel):
    search_id: UUID
    provider: str = Field(min_length=1, max_length=64)
    provider_job_id: str = Field(min_length=1, max_length=255)
    state: Literal["saved", "applied"] = "saved"


class SavedJobPatch(BaseModel):
    state: Literal["saved", "applied"]


class SavedJobRead(JobResult):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    profile_id: UUID
    state: Literal["saved", "applied"]
    saved_at: datetime
    applied_at: datetime | None = None
    updated_at: datetime


class SearchCreate(BaseModel):
    profile_id: UUID
    filters: SearchFilters | None = None


class SearchPage(BaseModel):
    search_id: UUID
    status: Literal["loading", "complete", "failed"]
    progress: float = Field(ge=0, le=1)
    checked_count: int = 0
    items: list[JobResult]
    page: int
    page_size: int
    total: int | None = None
    is_complete: bool
    warnings: list[str] = Field(default_factory=list)
