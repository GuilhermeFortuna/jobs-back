"""Shared pytest fixtures. Integration tests require DATABASE_URL (PostgreSQL)."""

from __future__ import annotations

import os
from collections.abc import Generator
from uuid import UUID, uuid4

import pytest

os.environ.setdefault("APP_ENV", "test")
from alembic import command
from alembic.config import Config
from alembic.util.exc import CommandError
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from jobs_back.api.searches import get_manager
from jobs_back.config import get_settings
from jobs_back.db import get_db
from jobs_back.main import create_app
from jobs_back.schemas.discovery import JobResult, SearchFilters
from jobs_back.search.live import LiveSearchManager, SearchState
from tests.helpers.fake_provider import FakeProvider

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
    try:
        command.upgrade(alembic_cfg, "head")
    except CommandError:
        with eng.begin() as connection:
            connection.execute(text("DELETE FROM jobs"))
        command.upgrade(alembic_cfg, "head")
    with eng.begin() as connection:
        connection.execute(text("TRUNCATE TABLE saved_jobs, profiles RESTART IDENTITY"))

    try:
        yield eng
    finally:
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
            connection.execute(text("TRUNCATE TABLE saved_jobs, profiles"))
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


@pytest.fixture
def search_manager() -> LiveSearchManager:
    return LiveSearchManager(provider=FakeProvider(total_pages=1, items_per_page=0))


def seed_search(
    manager: LiveSearchManager,
    profile_id: UUID,
    items: list[JobResult],
    *,
    search_id: UUID | None = None,
) -> UUID:
    sid = search_id or uuid4()
    state = SearchState(
        id=sid,
        profile_id=profile_id,
        filters=SearchFilters(),
        status="complete",
        progress=1,
        items=items,
    )
    manager.states[sid] = state
    return sid


@pytest.fixture
def api_client_with_search(
    db_session: Session,
    search_manager: LiveSearchManager,
) -> Generator[tuple[TestClient, LiveSearchManager], None, None]:
    app = create_app()

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    def override_get_manager() -> LiveSearchManager:
        return search_manager

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_manager] = override_get_manager
    with TestClient(app) as client:
        yield client, search_manager
    app.dependency_overrides.clear()
