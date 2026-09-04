from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from jobs_back.api.searches import get_manager
from jobs_back.db import get_db
from jobs_back.main import create_app
from jobs_back.models.profile import Profile
from jobs_back.models.saved_job import SavedJob
from jobs_back.schemas.discovery import SearchFilters
from jobs_back.search.live import LiveSearchManager
from tests.helpers.fake_provider import FakeProvider


@pytest.fixture
def search_client(db_session) -> tuple[TestClient, LiveSearchManager]:
    manager = LiveSearchManager(provider=FakeProvider(total_pages=1, items_per_page=1))
    app = create_app()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_manager] = lambda: manager
    with TestClient(app) as client:
        yield client, manager
    app.dependency_overrides.clear()


def test_search_does_not_create_library_rows(search_client, db_session) -> None:
    client, _manager = search_client
    profiles_before = db_session.scalar(select(func.count()).select_from(Profile)) or 0
    saved_before = db_session.scalar(select(func.count()).select_from(SavedJob)) or 0
    profile = client.post(
        "/profiles",
        json={
            "display_name": "No Persist",
            "preferences": SearchFilters(seniority=["senior"]).model_dump(),
        },
    ).json()
    response = client.post("/searches", json={"profile_id": profile["id"]})
    assert response.status_code == 202
    profiles_after = db_session.scalar(select(func.count()).select_from(Profile)) or 0
    saved_after = db_session.scalar(select(func.count()).select_from(SavedJob)) or 0
    assert profiles_after == profiles_before + 1
    assert saved_after == saved_before
