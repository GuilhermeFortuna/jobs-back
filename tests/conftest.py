"""Shared pytest fixtures. Integration tests require DATABASE_URL (PostgreSQL)."""

from __future__ import annotations

import os
from collections.abc import Generator

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from jobs_back.config import get_settings
from jobs_back.db import get_db
from jobs_back.main import create_app

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _database_url() -> str | None:
    return os.environ.get("TEST_DATABASE_URL")


@pytest.fixture(scope="session")
def database_url() -> Generator[str, None, None]:
    url = _database_url()
    if not url:
        pytest.fail(
            "TEST_DATABASE_URL is required for PostgreSQL integration tests; "
            "the normal DATABASE_URL is never used because the test schema is reset",
        )
    if not url.startswith("postgresql"):
        pytest.fail("TEST_DATABASE_URL must use PostgreSQL")

    database_name = (make_url(url).database or "").lower()
    if "test" not in database_name:
        pytest.fail("TEST_DATABASE_URL database name must contain 'test'")

    original_database_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = url
    get_settings.cache_clear()
    try:
        yield url
    finally:
        if original_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = original_database_url
        get_settings.cache_clear()


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

    try:
        yield eng
    finally:
        command.downgrade(alembic_cfg, "base")
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


@pytest.fixture
def committed_engine(database_url: str) -> Generator[Engine, None, None]:
    """Engine that commits changes (for lock contention and CLI subprocess tests)."""
    eng = create_engine(database_url, pool_pre_ping=True)
    alembic_cfg = Config(os.path.join(REPO_ROOT, "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(alembic_cfg, "head")
    try:
        yield eng
    finally:
        with eng.begin() as connection:
            connection.execute(text("TRUNCATE TABLE sync_runs, jobs"))
        eng.dispose()


@pytest.fixture
def committed_session(committed_engine: Engine) -> Generator[Session, None, None]:
    SessionLocal = sessionmaker(
        bind=committed_engine,
        autocommit=False,
        autoflush=False,
    )
    session = SessionLocal()
    try:
        yield session
        session.commit()
    finally:
        session.close()


@pytest.fixture
def api_client(db_session: Session) -> Generator[TestClient, None, None]:
    app = create_app()

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
