"""PostgreSQL migration tests for revision 005."""

from __future__ import annotations

import os
import uuid
from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from jobs_back.normalization.dedup import derive_dedup_key
from jobs_back.schemas.discovery import JobResult

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def alembic_config(database_url: str) -> Config:
    cfg = Config(os.path.join(REPO_ROOT, "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", database_url)
    return cfg


def _restore_head(database_url: str, alembic_config: Config) -> None:
    command.upgrade(alembic_config, "head")


@pytest.fixture(autouse=True)
def restore_alembic_head(
    alembic_config: Config, database_url: str
) -> Generator[None, None, None]:
    yield
    _restore_head(database_url, alembic_config)


def test_upgrade_adds_dedup_columns(database_url: str, alembic_config: Config) -> None:
    command.downgrade(alembic_config, "004_profiles_saved_jobs")
    command.upgrade(alembic_config, "005_saved_job_dedup")

    engine = create_engine(database_url)
    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("saved_jobs")}
    constraints = {
        constraint["name"]
        for constraint in inspector.get_unique_constraints("saved_jobs")
    }
    engine.dispose()

    assert "dedup_key" in columns
    assert "alternate_sources" in columns
    assert "uq_saved_jobs_profile_dedup" in constraints


def test_backfill_matches_runtime_dedup_key(
    database_url: str, alembic_config: Config
) -> None:
    command.downgrade(alembic_config, "004_profiles_saved_jobs")

    profile_id = uuid.uuid4()
    job_id = uuid.uuid4()
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO profiles (id, display_name, preferences)
                VALUES (:id, 'Migration Profile', '{}'::jsonb)
                """
            ),
            {"id": profile_id},
        )
        connection.execute(
            text(
                """
                INSERT INTO saved_jobs (
                    id, profile_id, provider, provider_job_id, state, title, company,
                    employment_type, remote_type, job_url, provider_payload, saved_at,
                    updated_at
                ) VALUES (
                    :id, :profile_id, 'himalayas', 'h-1', 'saved',
                    'Senior Python Developer',
                    'Acme Corp, Inc.', 'full_time', 'remote',
                    'https://example.com/jobs/1',
                    '{}'::jsonb, NOW(), NOW()
                )
                """
            ),
            {"id": job_id, "profile_id": profile_id},
        )
    engine.dispose()

    command.upgrade(alembic_config, "005_saved_job_dedup")

    runtime_key = derive_dedup_key(
        JobResult(
            provider="himalayas",
            provider_job_id="h-1",
            title="Senior Python Developer",
            company="Acme Corp, Inc.",
            job_url="https://example.com/jobs/1",
        )
    )

    engine = create_engine(database_url)
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT dedup_key, alternate_sources FROM saved_jobs WHERE id = :id"),
            {"id": job_id},
        ).one()
    engine.dispose()

    assert row.dedup_key == runtime_key
    assert row.alternate_sources == []


def test_collision_fold_keeps_applied_row_and_folds_alternate(
    database_url: str, alembic_config: Config
) -> None:
    command.downgrade(alembic_config, "004_profiles_saved_jobs")

    profile_id = uuid.uuid4()
    saved_id = uuid.uuid4()
    applied_id = uuid.uuid4()
    earlier = datetime(2026, 1, 1, tzinfo=UTC)
    later = datetime(2026, 1, 2, tzinfo=UTC)
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO profiles (id, display_name, preferences)
                VALUES (:id, 'Collision Profile', '{}'::jsonb)
                """
            ),
            {"id": profile_id},
        )
        connection.execute(
            text(
                """
                INSERT INTO saved_jobs (
                    id, profile_id, provider, provider_job_id, state, title, company,
                    employment_type, remote_type, job_url, provider_payload, saved_at,
                    updated_at, applied_at
                ) VALUES (
                    :id, :profile_id, 'himalayas', 'h-1', 'saved',
                    'Backend Engineer', 'Acme Corp', 'full_time', 'remote',
                    'https://example.com/h', '{}'::jsonb, :saved_at, :saved_at, NULL
                )
                """
            ),
            {"id": saved_id, "profile_id": profile_id, "saved_at": later},
        )
        connection.execute(
            text(
                """
                INSERT INTO saved_jobs (
                    id, profile_id, provider, provider_job_id, state, title, company,
                    employment_type, remote_type, job_url, provider_payload, saved_at,
                    updated_at, applied_at
                ) VALUES (
                    :id, :profile_id, 'remoteok', 'r-1', 'applied',
                    'Backend Engineer', 'Acme Corp, Inc.', 'full_time', 'remote',
                    'https://example.com/r', '{}'::jsonb,
                    :saved_at, :saved_at, :saved_at
                )
                """
            ),
            {
                "id": applied_id,
                "profile_id": profile_id,
                "saved_at": earlier,
            },
        )
    engine.dispose()

    command.upgrade(alembic_config, "005_saved_job_dedup")

    engine = create_engine(database_url)
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                """
                SELECT id, provider, alternate_sources
                FROM saved_jobs
                WHERE profile_id = :profile_id
                """
            ),
            {"profile_id": profile_id},
        ).fetchall()
    engine.dispose()

    assert len(rows) == 1
    assert rows[0].provider == "remoteok"
    alternates = rows[0].alternate_sources
    assert len(alternates) == 1
    assert alternates[0]["provider"] == "himalayas"


def test_downgrade_drops_dedup_columns(
    database_url: str, alembic_config: Config
) -> None:
    command.downgrade(alembic_config, "004_profiles_saved_jobs")
    command.upgrade(alembic_config, "005_saved_job_dedup")
    command.downgrade(alembic_config, "004_profiles_saved_jobs")

    engine = create_engine(database_url)
    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("saved_jobs")}
    engine.dispose()

    assert "dedup_key" not in columns
    assert "alternate_sources" not in columns
