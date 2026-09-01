"""PostgreSQL migration tests for revision 006."""

from __future__ import annotations

import os
import uuid
from collections.abc import Generator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

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


def test_upgrade_adds_skills_column(database_url: str, alembic_config: Config) -> None:
    command.downgrade(alembic_config, "005_saved_job_dedup")
    command.upgrade(alembic_config, "006_profile_skills")

    engine = create_engine(database_url)
    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("profiles")}
    engine.dispose()

    assert "skills" in columns


def test_existing_profile_defaults_to_empty_skills(
    database_url: str, alembic_config: Config
) -> None:
    command.downgrade(alembic_config, "005_saved_job_dedup")

    profile_id = uuid.uuid4()
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO profiles (id, display_name, preferences)
                VALUES (:id, 'Skills Migration Profile', '{}'::jsonb)
                """
            ),
            {"id": profile_id},
        )
    engine.dispose()

    command.upgrade(alembic_config, "006_profile_skills")

    engine = create_engine(database_url)
    with engine.connect() as connection:
        skills = connection.execute(
            text("SELECT skills FROM profiles WHERE id = :id"),
            {"id": profile_id},
        ).scalar_one()
    engine.dispose()

    assert skills == []


def test_downgrade_drops_skills_column(
    database_url: str, alembic_config: Config
) -> None:
    command.downgrade(alembic_config, "005_saved_job_dedup")
    command.upgrade(alembic_config, "006_profile_skills")
    command.downgrade(alembic_config, "005_saved_job_dedup")

    engine = create_engine(database_url)
    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("profiles")}
    engine.dispose()

    assert "skills" not in columns
