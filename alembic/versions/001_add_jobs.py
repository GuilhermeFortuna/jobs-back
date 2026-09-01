"""add jobs table

Revision ID: 001_add_jobs
Revises:
Create Date: 2026-09-01 00:20:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001_add_jobs"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("provider_job_id", sa.String(length=255), nullable=False),
        sa.Column(
            "raw_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("company", sa.String(length=512), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("employment_type", sa.String(length=32), nullable=False),
        sa.Column("remote_type", sa.String(length=32), nullable=False),
        sa.Column("location_text", sa.String(length=512), nullable=True),
        sa.Column("city", sa.String(length=255), nullable=True),
        sa.Column("region", sa.String(length=255), nullable=True),
        sa.Column("country_code", sa.String(length=2), nullable=True),
        sa.Column(
            "eligible_country_codes",
            postgresql.ARRAY(sa.Text()),
            nullable=True,
        ),
        sa.Column("salary_min", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("salary_max", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("salary_currency", sa.String(length=3), nullable=True),
        sa.Column("salary_period", sa.String(length=16), nullable=True),
        sa.Column(
            "salary_min_annual",
            sa.Numeric(precision=14, scale=2),
            nullable=True,
        ),
        sa.Column(
            "salary_max_annual",
            sa.Numeric(precision=14, scale=2),
            nullable=True,
        ),
        sa.Column("job_url", sa.Text(), nullable=False),
        sa.Column("apply_url", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default=sa.text("'active'"),
            nullable=False,
        ),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "discovered_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("inactive_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "length(trim(provider)) > 0",
            name="ck_jobs_provider_nonempty",
        ),
        sa.CheckConstraint(
            "length(trim(provider_job_id)) > 0",
            name="ck_jobs_provider_job_id_nonempty",
        ),
        sa.CheckConstraint(
            "length(trim(title)) > 0",
            name="ck_jobs_title_nonempty",
        ),
        sa.CheckConstraint(
            "length(trim(company)) > 0",
            name="ck_jobs_company_nonempty",
        ),
        sa.CheckConstraint(
            "length(trim(job_url)) > 0",
            name="ck_jobs_job_url_nonempty",
        ),
        sa.CheckConstraint(
            "employment_type IN ("
            "'full_time', 'part_time', 'contract', 'temporary', "
            "'internship', 'other', 'unspecified')",
            name="ck_jobs_employment_type",
        ),
        sa.CheckConstraint(
            "remote_type IN ('remote', 'hybrid', 'on_site', 'unspecified')",
            name="ck_jobs_remote_type",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'inactive')",
            name="ck_jobs_status",
        ),
        sa.CheckConstraint(
            "salary_period IS NULL OR salary_period IN ("
            "'hourly', 'daily', 'weekly', 'monthly', 'yearly', 'other')",
            name="ck_jobs_salary_period",
        ),
        sa.CheckConstraint(
            "salary_min IS NULL OR salary_min > 0",
            name="ck_jobs_salary_min_positive",
        ),
        sa.CheckConstraint(
            "salary_max IS NULL OR salary_max > 0",
            name="ck_jobs_salary_max_positive",
        ),
        sa.CheckConstraint(
            "salary_min_annual IS NULL OR salary_min_annual > 0",
            name="ck_jobs_salary_min_annual_positive",
        ),
        sa.CheckConstraint(
            "salary_max_annual IS NULL OR salary_max_annual > 0",
            name="ck_jobs_salary_max_annual_positive",
        ),
        sa.CheckConstraint(
            "salary_min IS NULL OR salary_max IS NULL OR salary_min <= salary_max",
            name="ck_jobs_salary_range_ordered",
        ),
        sa.CheckConstraint(
            "salary_min_annual IS NULL OR salary_max_annual IS NULL "
            "OR salary_min_annual <= salary_max_annual",
            name="ck_jobs_salary_annual_range_ordered",
        ),
        sa.CheckConstraint(
            "(status = 'active' AND inactive_at IS NULL) "
            "OR (status = 'inactive' AND inactive_at IS NOT NULL)",
            name="ck_jobs_lifecycle_inactive_at",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider",
            "provider_job_id",
            name="uq_jobs_provider_identity",
        ),
    )
    op.create_index(
        "ix_jobs_status_posted_at_id",
        "jobs",
        ["status", "posted_at", "id"],
        unique=False,
    )
    op.create_index(
        "ix_jobs_provider_status",
        "jobs",
        ["provider", "status"],
        unique=False,
    )
    op.create_index(
        "ix_jobs_eligible_country_codes",
        "jobs",
        ["eligible_country_codes"],
        unique=False,
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_jobs_eligible_country_codes",
        table_name="jobs",
        postgresql_using="gin",
    )
    op.drop_index("ix_jobs_provider_status", table_name="jobs")
    op.drop_index("ix_jobs_status_posted_at_id", table_name="jobs")
    op.drop_table("jobs")
