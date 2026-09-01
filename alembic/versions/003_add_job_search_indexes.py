"""add job search indexes

Revision ID: 003_add_job_search_indexes
Revises: 002_add_sync_runs
Create Date: 2026-09-01 02:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

from jobs_back.search.constants import JOB_SEARCH_VECTOR_SQL

# revision identifiers, used by Alembic.
revision: str = "003_add_job_search_indexes"
down_revision: str | None = "002_add_sync_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
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


def downgrade() -> None:
    op.drop_index("ix_jobs_salary_currency_annual", table_name="jobs")
    op.drop_index("ix_jobs_status_employment_type", table_name="jobs")
    op.drop_index("ix_jobs_status_remote_type", table_name="jobs")
    op.execute("DROP INDEX IF EXISTS ix_jobs_search_vector")
