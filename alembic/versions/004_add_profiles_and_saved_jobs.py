"""add trusted profiles and personal job library

Revision ID: 004_profiles_saved_jobs
Revises: 003_add_job_search_indexes
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from alembic.util.exc import CommandError
from sqlalchemy.dialects import postgresql

from jobs_back.search.constants import JOB_SEARCH_VECTOR_SQL

revision: str = "004_profiles_saved_jobs"
down_revision: str | None = "003_add_job_search_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _legacy_catalog_counts(connection: sa.Connection) -> tuple[int, int]:
    jobs_count = connection.execute(sa.text("SELECT COUNT(*) FROM jobs")).scalar_one()
    sync_runs_count = connection.execute(
        sa.text("SELECT COUNT(*) FROM sync_runs")
    ).scalar_one()
    return int(jobs_count), int(sync_runs_count)


def _drop_legacy_catalog() -> None:
    op.execute("DROP INDEX IF EXISTS ix_jobs_search_vector")
    op.drop_index("ix_jobs_salary_currency_annual", table_name="jobs")
    op.drop_index("ix_jobs_status_employment_type", table_name="jobs")
    op.drop_index("ix_jobs_status_remote_type", table_name="jobs")
    op.drop_index(
        "ix_jobs_eligible_country_codes",
        table_name="jobs",
        postgresql_using="gin",
    )
    op.drop_index("ix_jobs_provider_status", table_name="jobs")
    op.drop_index("ix_jobs_status_posted_at_id", table_name="jobs")
    op.drop_table("jobs")
    op.drop_index("ix_sync_runs_provider_started_at", table_name="sync_runs")
    op.drop_index("ix_sync_runs_provider_status", table_name="sync_runs")
    op.drop_table("sync_runs")


def _recreate_legacy_catalog() -> None:
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
    op.execute(
        f"CREATE INDEX ix_jobs_search_vector ON jobs "
        f"USING gin ({JOB_SEARCH_VECTOR_SQL})"
    )
    op.create_index(
        "ix_jobs_status_remote_type",
        "jobs",
        ["status", "remote_type"],
        unique=False,
    )
    op.create_index(
        "ix_jobs_status_employment_type",
        "jobs",
        ["status", "employment_type"],
        unique=False,
    )
    op.create_index(
        "ix_jobs_salary_currency_annual",
        "jobs",
        ["salary_currency", "salary_min_annual", "salary_max_annual"],
        unique=False,
    )

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


def upgrade() -> None:
    op.create_table(
        "profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("display_name", sa.String(80), nullable=False),
        sa.Column(
            "preferences",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("length(trim(display_name)) > 0", name="ck_profiles_name"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("display_name"),
    )
    op.create_table(
        "saved_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("provider_job_id", sa.String(255), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("company", sa.String(512), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("location_text", sa.String(512)),
        sa.Column("eligible_country_codes", postgresql.ARRAY(sa.Text())),
        sa.Column("employment_type", sa.String(32), nullable=False),
        sa.Column("remote_type", sa.String(32), nullable=False),
        sa.Column("seniority", sa.String(80)),
        sa.Column("salary_min_annual", sa.Numeric(14, 2)),
        sa.Column("salary_max_annual", sa.Numeric(14, 2)),
        sa.Column("salary_currency", sa.String(3)),
        sa.Column("job_url", sa.Text(), nullable=False),
        sa.Column("apply_url", sa.Text()),
        sa.Column("company_logo_url", sa.Text()),
        sa.Column("posted_at", sa.DateTime(timezone=True)),
        sa.Column("provider_payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "saved_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("applied_at", sa.DateTime(timezone=True)),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("state IN ('saved', 'applied')", name="ck_saved_jobs_state"),
        sa.CheckConstraint(
            "(state = 'saved' AND applied_at IS NULL) OR "
            "(state = 'applied' AND applied_at IS NOT NULL)",
            name="ck_saved_jobs_applied_at",
        ),
        sa.CheckConstraint(
            "salary_min_annual IS NULL OR salary_min_annual > 0",
            name="ck_saved_jobs_salary_min_annual_positive",
        ),
        sa.CheckConstraint(
            "salary_max_annual IS NULL OR salary_max_annual > 0",
            name="ck_saved_jobs_salary_max_annual_positive",
        ),
        sa.CheckConstraint(
            "salary_min_annual IS NULL OR salary_max_annual IS NULL "
            "OR salary_min_annual <= salary_max_annual",
            name="ck_saved_jobs_salary_annual_range_ordered",
        ),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "profile_id",
            "provider",
            "provider_job_id",
            name="uq_saved_jobs_profile_provider",
        ),
    )
    op.create_index("ix_saved_jobs_profile_id", "saved_jobs", ["profile_id"])
    op.create_index(
        "ix_saved_jobs_profile_state_saved_at",
        "saved_jobs",
        ["profile_id", "state", sa.text("saved_at DESC")],
        unique=False,
    )

    connection = op.get_bind()
    jobs_count, sync_runs_count = _legacy_catalog_counts(connection)
    if jobs_count > 0 or sync_runs_count > 0:
        raise CommandError(
            "Migration 004 refuses to drop legacy catalog data: "
            f"jobs={jobs_count}, sync_runs={sync_runs_count}. "
            "Export or migrate Batch 01 catalog rows before upgrading."
        )
    _drop_legacy_catalog()


def downgrade() -> None:
    _recreate_legacy_catalog()
    op.drop_index("ix_saved_jobs_profile_state_saved_at", table_name="saved_jobs")
    op.drop_index("ix_saved_jobs_profile_id", table_name="saved_jobs")
    op.drop_table("saved_jobs")
    op.drop_table("profiles")
