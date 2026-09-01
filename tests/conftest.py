"""Shared pytest fixtures. Integration tests require DATABASE_URL (PostgreSQL)."""

from __future__ import annotations

import os
from collections.abc import Generator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _database_url() -> str | None:
    return os.environ.get("DATABASE_URL") or os.environ.get("TEST_DATABASE_URL")


@pytest.fixture(scope="session")
def database_url() -> str:
    url = _database_url()
    if not url:
        pytest.skip(
            "DATABASE_URL or TEST_DATABASE_URL is required "
            "for PostgreSQL integration tests"
        )
    if not url.startswith("postgresql"):
        pytest.skip("Integration tests require a PostgreSQL DATABASE_URL")
    return url


@pytest.fixture(scope="session")
def engine(database_url: str) -> Generator[Engine, None, None]:
    eng = create_engine(database_url, pool_pre_ping=True)
    with eng.connect() as conn:
        conn.execute(text("SELECT 1"))

    alembic_cfg = Config(os.path.join(REPO_ROOT, "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)
    # Ensure a clean schema for the session, then upgrade to head.
    command.downgrade(alembic_cfg, "base")
    command.upgrade(alembic_cfg, "head")

    yield eng
    eng.dispose()


@pytest.fixture
def db_session(engine: Engine) -> Generator[Session, None, None]:
    connection = engine.connect()
    transaction = connection.begin()
    SessionLocal = sessionmaker(bind=connection, autocommit=False, autoflush=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()
