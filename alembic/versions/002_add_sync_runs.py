"""add sync_runs table

Revision ID: 002_add_sync_runs
Revises: 001_add_jobs
Create Date: 2026-09-01 01:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "002_add_sync_runs"
down_revision: str | None = "001_add_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sync_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("trigger", sa.String(length=16), nullable=False),
        sa.Column("sync_mode", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "fetched",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "created",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "updated",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "unchanged",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "reactivated",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "deactivated",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(trim(provider)) > 0",
            name="ck_sync_runs_provider_nonempty",
        ),
        sa.CheckConstraint(
            "trigger IN ('manual')",
            name="ck_sync_runs_trigger",
        ),
        sa.CheckConstraint(
            "sync_mode IN ('full_snapshot', 'incremental')",
            name="ck_sync_runs_sync_mode",
        ),
        sa.CheckConstraint(
            "status IN ('running', 'succeeded', 'failed')",
            name="ck_sync_runs_status",
        ),
        sa.CheckConstraint(
            "(status = 'running' AND finished_at IS NULL) "
            "OR (status IN ('succeeded', 'failed') AND finished_at IS NOT NULL)",
            name="ck_sync_runs_finished_at",
        ),
        sa.CheckConstraint("fetched >= 0", name="ck_sync_runs_fetched_nonneg"),
        sa.CheckConstraint("created >= 0", name="ck_sync_runs_created_nonneg"),
        sa.CheckConstraint("updated >= 0", name="ck_sync_runs_updated_nonneg"),
        sa.CheckConstraint("unchanged >= 0", name="ck_sync_runs_unchanged_nonneg"),
        sa.CheckConstraint(
            "reactivated >= 0",
            name="ck_sync_runs_reactivated_nonneg",
        ),
        sa.CheckConstraint(
            "deactivated >= 0",
            name="ck_sync_runs_deactivated_nonneg",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_sync_runs_provider_status",
        "sync_runs",
        ["provider", "status"],
        unique=False,
    )
    op.create_index(
        "ix_sync_runs_provider_started_at",
        "sync_runs",
        ["provider", sa.text("started_at DESC")],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_sync_runs_provider_started_at", table_name="sync_runs")
    op.drop_index("ix_sync_runs_provider_status", table_name="sync_runs")
    op.drop_table("sync_runs")
