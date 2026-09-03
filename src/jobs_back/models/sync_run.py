"""SQLAlchemy SyncRun model for provider ingestion run tracking."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from jobs_back.db import Base
from jobs_back.models.enums import SyncMode, SyncRunStatus, SyncTrigger


class SyncRun(Base):
    __tablename__ = "sync_runs"
    __table_args__ = (
        CheckConstraint(
            "length(trim(provider)) > 0",
            name="ck_sync_runs_provider_nonempty",
        ),
        CheckConstraint(
            "trigger IN ('manual')",
            name="ck_sync_runs_trigger",
        ),
        CheckConstraint(
            "sync_mode IN ('full_snapshot', 'incremental')",
            name="ck_sync_runs_sync_mode",
        ),
        CheckConstraint(
            "status IN ('running', 'succeeded', 'failed')",
            name="ck_sync_runs_status",
        ),
        CheckConstraint(
            "(status = 'running' AND finished_at IS NULL) "
            "OR (status IN ('succeeded', 'failed') AND finished_at IS NOT NULL)",
            name="ck_sync_runs_finished_at",
        ),
        CheckConstraint("fetched >= 0", name="ck_sync_runs_fetched_nonneg"),
        CheckConstraint("created >= 0", name="ck_sync_runs_created_nonneg"),
        CheckConstraint("updated >= 0", name="ck_sync_runs_updated_nonneg"),
        CheckConstraint("unchanged >= 0", name="ck_sync_runs_unchanged_nonneg"),
        CheckConstraint(
            "reactivated >= 0",
            name="ck_sync_runs_reactivated_nonneg",
        ),
        CheckConstraint(
            "deactivated >= 0",
            name="ck_sync_runs_deactivated_nonneg",
        ),
        Index("ix_sync_runs_provider_status", "provider", "status"),
        Index(
            "ix_sync_runs_provider_started_at",
            "provider",
            text("started_at DESC"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    trigger: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=SyncTrigger.MANUAL.value,
    )
    sync_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    fetched: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    created: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    updated: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    unchanged: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    reactivated: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    deactivated: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )

    def __repr__(self) -> str:
        return (
            f"SyncRun(id={self.id!s}, provider={self.provider!r}, "
            f"status={self.status!r})"
        )


__all__ = ["SyncRun", "SyncMode", "SyncRunStatus", "SyncTrigger"]
