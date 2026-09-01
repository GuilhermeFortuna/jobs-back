"""PostgreSQL migration tests for revision 004."""

from __future__ import annotations

import os
import uuid
from collections.abc import Generator

import pytest
from alembic import command
from alembic.config import Config
from alembic.util.exc import CommandError
from sqlalchemy import create_engine, inspect, text

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def alembic_config(database_url: str) -> Config:
    cfg = Config(os.path.join(REPO_ROOT, "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", database_url)
    return cfg


def _clear_legacy_jobs(database_url: str) -> None:
    engine = create_engine(database_url)
    inspector = inspect(engine)
    if "jobs" not in inspector.get_table_names():
        engine.dispose()
        return
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM jobs"))
    engine.dispose()


def _ensure_revision_003(database_url: str, alembic_config: Config) -> None:
    command.downgrade(alembic_config, "003_add_job_search_indexes")
    _clear_legacy_jobs(database_url)


def _restore_head(database_url: str, alembic_config: Config) -> None:
    _clear_legacy_jobs(database_url)
    command.upgrade(alembic_config, "head")


@pytest.fixture(autouse=True)
def restore_alembic_head(
    alembic_config: Config, database_url: str
) -> Generator[None, None, None]:
    yield
    _restore_head(database_url, alembic_config)


def test_upgrade_from_003_drops_empty_legacy_catalog(
    database_url: str, alembic_config: Config
) -> None:
    _ensure_revision_003(database_url, alembic_config)
    command.upgrade(alembic_config, "004_profiles_saved_jobs")

    engine = create_engine(database_url)
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    engine.dispose()

    assert "profiles" in tables
    assert "saved_jobs" in tables
    assert "jobs" not in tables
    assert "sync_runs" not in tables


def test_upgrade_refuses_nonempty_legacy_jobs(
    database_url: str, alembic_config: Config
) -> None:
    _ensure_revision_003(database_url, alembic_config)

    engine = create_engine(database_url)
    legacy_id = f"legacy-{uuid.uuid4().hex[:8]}"
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO jobs (
                    id, provider, provider_job_id, raw_payload, title, company,
                    employment_type, remote_type, job_url, status
                ) VALUES (
                    :id, 'example', :legacy_id, '{}', 'Legacy', 'Corp',
                    'full_time', 'remote', 'https://example.com/legacy', 'active'
                )
                """
            ),
            {"id": uuid.uuid4(), "legacy_id": legacy_id},
        )
    engine.dispose()

    with pytest.raises(CommandError, match="refuses to drop legacy catalog data"):
        command.upgrade(alembic_config, "004_profiles_saved_jobs")

    engine = create_engine(database_url)
    with engine.connect() as connection:
        count = connection.scalar(text("SELECT COUNT(*) FROM jobs"))
    engine.dispose()
    assert count == 1


def test_downgrade_from_004_restores_legacy_catalog(
    database_url: str, alembic_config: Config
) -> None:
    _restore_head(database_url, alembic_config)
    command.downgrade(alembic_config, "003_add_job_search_indexes")

    engine = create_engine(database_url)
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    engine.dispose()

    assert "jobs" in tables
    assert "sync_runs" in tables
    assert "profiles" not in tables
    assert "saved_jobs" not in tables
