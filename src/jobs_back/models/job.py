"""SQLAlchemy Job model for the normalized provider-neutral job record."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from jobs_back.db import Base
from jobs_back.models.enums import (
    EmploymentType,
    JobStatus,
    RemoteType,
)


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "provider_job_id",
            name="uq_jobs_provider_identity",
        ),
        CheckConstraint(
            "length(trim(provider)) > 0",
            name="ck_jobs_provider_nonempty",
        ),
        CheckConstraint(
            "length(trim(provider_job_id)) > 0",
            name="ck_jobs_provider_job_id_nonempty",
        ),
        CheckConstraint(
            "length(trim(title)) > 0",
            name="ck_jobs_title_nonempty",
        ),
        CheckConstraint(
            "length(trim(company)) > 0",
            name="ck_jobs_company_nonempty",
        ),
        CheckConstraint(
            "length(trim(job_url)) > 0",
            name="ck_jobs_job_url_nonempty",
        ),
        CheckConstraint(
            "employment_type IN ("
            "'full_time', 'part_time', 'contract', 'temporary', "
            "'internship', 'other', 'unspecified')",
            name="ck_jobs_employment_type",
        ),
        CheckConstraint(
            "remote_type IN ('remote', 'hybrid', 'on_site', 'unspecified')",
            name="ck_jobs_remote_type",
        ),
        CheckConstraint(
            "status IN ('active', 'inactive')",
            name="ck_jobs_status",
        ),
        CheckConstraint(
            "salary_period IS NULL OR salary_period IN ("
            "'hourly', 'daily', 'weekly', 'monthly', 'yearly', 'other')",
            name="ck_jobs_salary_period",
        ),
        CheckConstraint(
            "salary_min IS NULL OR salary_min > 0",
            name="ck_jobs_salary_min_positive",
        ),
        CheckConstraint(
            "salary_max IS NULL OR salary_max > 0",
            name="ck_jobs_salary_max_positive",
        ),
        CheckConstraint(
            "salary_min_annual IS NULL OR salary_min_annual > 0",
            name="ck_jobs_salary_min_annual_positive",
        ),
        CheckConstraint(
            "salary_max_annual IS NULL OR salary_max_annual > 0",
            name="ck_jobs_salary_max_annual_positive",
        ),
        CheckConstraint(
            "salary_min IS NULL OR salary_max IS NULL OR salary_min <= salary_max",
            name="ck_jobs_salary_range_ordered",
        ),
        CheckConstraint(
            "salary_min_annual IS NULL OR salary_max_annual IS NULL "
            "OR salary_min_annual <= salary_max_annual",
            name="ck_jobs_salary_annual_range_ordered",
        ),
        CheckConstraint(
            "(status = 'active' AND inactive_at IS NULL) "
            "OR (status = 'inactive' AND inactive_at IS NOT NULL)",
            name="ck_jobs_lifecycle_inactive_at",
        ),
        Index("ix_jobs_status_posted_at_id", "status", "posted_at", "id"),
        Index("ix_jobs_provider_status", "provider", "status"),
        Index(
            "ix_jobs_eligible_country_codes",
            "eligible_country_codes",
            postgresql_using="gin",
        ),
        Index("ix_jobs_status_remote_type", "status", "remote_type"),
        Index("ix_jobs_status_employment_type", "status", "employment_type"),
        Index(
            "ix_jobs_salary_currency_annual",
            "salary_currency",
            "salary_min_annual",
            "salary_max_annual",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_job_id: Mapped[str] = mapped_column(String(255), nullable=False)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    title: Mapped[str] = mapped_column(String(512), nullable=False)
    company: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    employment_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=EmploymentType.UNSPECIFIED.value,
    )
    remote_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=RemoteType.UNSPECIFIED.value,
    )

    location_text: Mapped[str | None] = mapped_column(String(512), nullable=True)
    city: Mapped[str | None] = mapped_column(String(255), nullable=True)
    region: Mapped[str | None] = mapped_column(String(255), nullable=True)
    country_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    eligible_country_codes: Mapped[list[str] | None] = mapped_column(
        ARRAY(Text),
        nullable=True,
    )

    salary_min: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    salary_max: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    salary_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    salary_period: Mapped[str | None] = mapped_column(String(16), nullable=True)
    salary_min_annual: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2),
        nullable=True,
    )
    salary_max_annual: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2),
        nullable=True,
    )

    job_url: Mapped[str] = mapped_column(Text, nullable=False)
    apply_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=JobStatus.ACTIVE.value,
        server_default=text("'active'"),
    )
    posted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    inactive_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    def __repr__(self) -> str:
        return (
            f"Job(id={self.id!s}, provider={self.provider!r}, "
            f"provider_job_id={self.provider_job_id!r})"
        )


# Re-export enum types used alongside the model for convenience.
__all__ = [
    "Job",
]
