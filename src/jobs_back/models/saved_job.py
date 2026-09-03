from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    desc,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from jobs_back.db import Base


class SavedJob(Base):
    __tablename__ = "saved_jobs"
    __table_args__ = (
        UniqueConstraint(
            "profile_id",
            "provider",
            "provider_job_id",
            name="uq_saved_jobs_profile_provider",
        ),
        UniqueConstraint(
            "profile_id",
            "dedup_key",
            name="uq_saved_jobs_profile_dedup",
        ),
        CheckConstraint("state IN ('saved', 'applied')", name="ck_saved_jobs_state"),
        CheckConstraint(
            "(state = 'saved' AND applied_at IS NULL) OR "
            "(state = 'applied' AND applied_at IS NOT NULL)",
            name="ck_saved_jobs_applied_at",
        ),
        CheckConstraint(
            "salary_min_annual IS NULL OR salary_min_annual > 0",
            name="ck_saved_jobs_salary_min_annual_positive",
        ),
        CheckConstraint(
            "salary_max_annual IS NULL OR salary_max_annual > 0",
            name="ck_saved_jobs_salary_max_annual_positive",
        ),
        CheckConstraint(
            "salary_min_annual IS NULL OR salary_max_annual IS NULL "
            "OR salary_min_annual <= salary_max_annual",
            name="ck_saved_jobs_salary_annual_range_ordered",
        ),
        Index(
            "ix_saved_jobs_profile_state_saved_at",
            "profile_id",
            "state",
            desc("saved_at"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_job_id: Mapped[str] = mapped_column(String(255), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="saved")
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    company: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    location_text: Mapped[str | None] = mapped_column(String(512))
    eligible_country_codes: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    employment_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="unspecified"
    )
    remote_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="remote"
    )
    seniority: Mapped[str | None] = mapped_column(String(80))
    salary_min_annual: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    salary_max_annual: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    salary_currency: Mapped[str | None] = mapped_column(String(3))
    job_url: Mapped[str] = mapped_column(Text, nullable=False)
    apply_url: Mapped[str | None] = mapped_column(Text)
    company_logo_url: Mapped[str | None] = mapped_column(Text)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dedup_key: Mapped[str] = mapped_column(Text, nullable=False)
    alternate_sources: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    provider_payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    saved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    profile = relationship("Profile", back_populates="jobs")
