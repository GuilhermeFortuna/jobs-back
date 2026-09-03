"""add saved job dedup identity and alternate sources

Revision ID: 005_saved_job_dedup
Revises: 004_profiles_saved_jobs

Downgrade drops the dedup constraint and columns without restoring folded rows.
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from jobs_back.normalization.dedup import derive_dedup_key
from jobs_back.schemas.discovery import JobResult

revision: str = "005_saved_job_dedup"
down_revision: str | None = "004_profiles_saved_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_STATE_RANK = {"saved": 0, "applied": 1}


def _row_to_job_result(row: sa.Row[Any]) -> JobResult:
    return JobResult(
        provider=row.provider,
        provider_job_id=row.provider_job_id,
        title=row.title,
        company=row.company,
        description=row.description,
        location_text=row.location_text,
        eligible_country_codes=row.eligible_country_codes,
        employment_type=row.employment_type,
        remote_type=row.remote_type,
        seniority=row.seniority,
        salary_min_annual=row.salary_min_annual,
        salary_max_annual=row.salary_max_annual,
        salary_currency=row.salary_currency,
        job_url=row.job_url,
        apply_url=row.apply_url,
        company_logo_url=row.company_logo_url,
        posted_at=row.posted_at,
    )


def _alternate_source_payload(row: sa.Row[Any]) -> dict[str, Any]:
    return {
        "provider": row.provider,
        "provider_job_id": row.provider_job_id,
        "job_url": row.job_url,
        "apply_url": row.apply_url,
    }


def _append_alternate(
    alternates: list[dict[str, Any]],
    source: dict[str, Any],
) -> list[dict[str, Any]]:
    identity = (source["provider"], source["provider_job_id"])
    if any(
        (item["provider"], item["provider_job_id"]) == identity for item in alternates
    ):
        return alternates
    return [*alternates, source]


def _pick_winner(rows: list[sa.Row[Any]]) -> sa.Row[Any]:
    return min(
        rows,
        key=lambda row: (
            -_STATE_RANK[row.state],
            row.saved_at or datetime.min.replace(tzinfo=row.saved_at.tzinfo),
            str(row.id),
        ),
    )


def upgrade() -> None:
    op.add_column("saved_jobs", sa.Column("dedup_key", sa.Text(), nullable=True))
    op.add_column(
        "saved_jobs",
        sa.Column(
            "alternate_sources",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )

    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            """
            SELECT
                id,
                profile_id,
                provider,
                provider_job_id,
                state,
                title,
                company,
                description,
                location_text,
                eligible_country_codes,
                employment_type,
                remote_type,
                seniority,
                salary_min_annual,
                salary_max_annual,
                salary_currency,
                job_url,
                apply_url,
                company_logo_url,
                posted_at,
                saved_at
            FROM saved_jobs
            ORDER BY profile_id, saved_at, id
            """
        )
    ).fetchall()

    dedup_keys: dict[UUID, str] = {}
    for row in rows:
        dedup_keys[row.id] = derive_dedup_key(_row_to_job_result(row))
        connection.execute(
            sa.text("UPDATE saved_jobs SET dedup_key = :dedup_key WHERE id = :id"),
            {"dedup_key": dedup_keys[row.id], "id": row.id},
        )

    grouped: dict[tuple[UUID, str], list[sa.Row[Any]]] = defaultdict(list)
    for row in rows:
        grouped[(row.profile_id, dedup_keys[row.id])].append(row)

    for group_rows in grouped.values():
        if len(group_rows) == 1:
            continue
        winner = _pick_winner(group_rows)
        alternates: list[dict[str, Any]] = []
        for row in group_rows:
            if row.id == winner.id:
                continue
            alternates = _append_alternate(alternates, _alternate_source_payload(row))
            connection.execute(
                sa.text("DELETE FROM saved_jobs WHERE id = :id"),
                {"id": row.id},
            )
        connection.execute(
            sa.text(
                """
                UPDATE saved_jobs
                SET alternate_sources = CAST(:payload AS jsonb)
                WHERE id = :id
                """
            ),
            {"payload": json.dumps(alternates), "id": winner.id},
        )

    op.alter_column("saved_jobs", "dedup_key", nullable=False)
    op.create_unique_constraint(
        "uq_saved_jobs_profile_dedup",
        "saved_jobs",
        ["profile_id", "dedup_key"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_saved_jobs_profile_dedup", "saved_jobs", type_="unique")
    op.drop_column("saved_jobs", "alternate_sources")
    op.drop_column("saved_jobs", "dedup_key")
