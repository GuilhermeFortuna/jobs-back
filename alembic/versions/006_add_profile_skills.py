"""add profile skills column

Revision ID: 006_profile_skills
Revises: 005_saved_job_dedup

Downgrade drops the skills column and discards stored skill data.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "006_profile_skills"
down_revision: str | None = "005_saved_job_dedup"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "profiles",
        sa.Column(
            "skills",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("profiles", "skills")
