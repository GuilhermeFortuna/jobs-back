from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from jobs_back.api.searches import get_manager
from jobs_back.db import get_db
from jobs_back.main import create_app
from jobs_back.schemas.discovery import SearchFilters
from jobs_back.search.live import LiveSearchManager
from tests.helpers.fake_provider import FakeProvider

SearchApiClient = tuple[TestClient, LiveSearchManager]


def _create_profile(client: TestClient, name: str) -> str:
    response = client.post("/profiles", json={"display_name": name})
    assert response.status_code == 201
    return response.json()["id"]


@pytest.fixture
def search_api_client(db_session: Session) -> SearchApiClient:
    provider = FakeProvider(total_pages=2, items_per_page=2, delay=0.01)
    manager = LiveSearchManager(provider=provider)
    app = create_app()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_manager] = lambda: manager
    with TestClient(app) as client:
        yield client, manager
    app.dependency_overrides.clear()
    asyncio.run(manager.close())


def test_create_search_returns_202(search_api_client: SearchApiClient) -> None:
    client, _manager = search_api_client
    profile_id = _create_profile(client, "Searcher")
    filters = SearchFilters(query="python").model_dump()
    response = client.post(
        "/searches",
        json={"profile_id": profile_id, "filters": filters},
    )
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "loading"
    assert body["total"] is None
    if body["items"]:
        assert "provider_payload" not in body["items"][0]


def test_get_search_eventually_completes(search_api_client: SearchApiClient) -> None:
    client, _manager = search_api_client
    profile_id = _create_profile(client, "Poller")
    created = client.post("/searches", json={"profile_id": profile_id})
    search_id = created.json()["search_id"]
    final = None
    for _ in range(50):
        response = client.get(f"/searches/{search_id}?profile_id={profile_id}")
        assert response.status_code == 200
        final = response.json()
        if final["is_complete"]:
            break
    assert final is not None
    assert final["status"] == "complete"
    assert final["total"] == 4


def test_get_missing_search_returns_404(search_api_client: SearchApiClient) -> None:
    client, _ = search_api_client
    profile_id = _create_profile(client, "Missing")
    response = client.get(f"/searches/{uuid4()}?profile_id={profile_id}")
    assert response.status_code == 404


def test_get_evicted_search_returns_410(search_api_client: SearchApiClient) -> None:
    client, manager = search_api_client
    profile_id = _create_profile(client, "Evicted")
    created = client.post("/searches", json={"profile_id": profile_id})
    search_id = UUID(created.json()["search_id"])
    manager._evict(search_id)
    response = client.get(f"/searches/{search_id}?profile_id={profile_id}")
    assert response.status_code == 410


def test_refresh_returns_stale_metadata(search_api_client: SearchApiClient) -> None:
    client, _manager = search_api_client
    profile_id = _create_profile(client, "Refresh")
    first = client.post(f"/profiles/{profile_id}/default-search/refresh")
    search_id = first.json()["search_id"]
    for _ in range(50):
        polled = client.get(f"/searches/{search_id}?profile_id={profile_id}")
        if polled.json()["is_complete"]:
            break
    second = client.post(f"/profiles/{profile_id}/default-search/refresh")
    assert second.status_code == 202
    body = second.json()
    assert body["previous_search_id"] == search_id
    assert body["serving_search_id"] == search_id
    assert (
        client.get(f"/searches/{search_id}?profile_id={profile_id}").status_code == 200
    )


def test_invalid_page_size_returns_422(search_api_client: SearchApiClient) -> None:
    client, _ = search_api_client
    profile_id = _create_profile(client, "Paging")
    response = client.get(f"/searches/{uuid4()}?profile_id={profile_id}&page_size=101")
    assert response.status_code == 422


def test_search_page_requires_the_owning_profile(
    search_api_client: SearchApiClient,
) -> None:
    client, _ = search_api_client
    owner_id = _create_profile(client, "Owner")
    other_id = _create_profile(client, "Other")
    created = client.post("/searches", json={"profile_id": owner_id})
    search_id = created.json()["search_id"]

    assert client.get(f"/searches/{search_id}?profile_id={owner_id}").status_code == 200
    assert client.get(f"/searches/{search_id}?profile_id={other_id}").status_code == 404


def test_search_page_without_a_profile_is_rejected(
    search_api_client: SearchApiClient,
) -> None:
    client, _ = search_api_client
    profile_id = _create_profile(client, "Anonymous")
    created = client.post("/searches", json={"profile_id": profile_id})
    search_id = created.json()["search_id"]
    assert client.get(f"/searches/{search_id}").status_code == 422
