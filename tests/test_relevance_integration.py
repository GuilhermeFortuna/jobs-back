"""Integration tests for relevance ranking in live search."""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from jobs_back.api.searches import get_manager
from jobs_back.db import get_db
from jobs_back.main import create_app
from jobs_back.schemas.discovery import SearchFilters
from jobs_back.search.live import LiveSearchManager
from tests.helpers.discovery import make_job_result
from tests.helpers.fake_provider import FakeProvider

SearchApiClient = tuple[TestClient, LiveSearchManager]


def _jobs() -> list:
    return [
        make_job_result(
            provider="alpha",
            provider_job_id="a-1",
            title="Python Engineer",
            description="Django APIs",
            posted_at=None,
        ),
        make_job_result(
            provider="beta",
            provider_job_id="b-1",
            title="Java Engineer",
            description="Spring services",
            posted_at=None,
        ),
        make_job_result(
            provider="alpha",
            provider_job_id="a-2",
            title="Python Django Developer",
            description="Full stack",
            posted_at=None,
        ),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("completion_orders", [[1], [1, 1], [1, 1, 1]])
async def test_order_independence_for_identical_result_sets(
    completion_orders: list[int],
) -> None:
    items = _jobs()

    class StaticOrderProvider(FakeProvider):
        def __init__(self, *, key: str, order: list[int]) -> None:
            super().__init__(
                key=key,
                total_pages=1,
                items_per_page=0,
                completion_order=order,
            )
            self._items = [item for item in items if item.provider == key]

        async def pages(self, filters):
            from jobs_back.providers.protocol import ProviderPageBatch

            del filters
            yield ProviderPageBatch(items=self._items, page=1, total_pages=1)

    manager = LiveSearchManager(
        providers=[
            StaticOrderProvider(key="alpha", order=completion_orders[:1]),
            StaticOrderProvider(key="beta", order=completion_orders[1:2] or [1]),
        ]
    )
    skills = [{"label": "Python", "token": "python"}]
    started = manager.start(
        uuid4(),
        SearchFilters(query="python django", sort="relevance"),
        profile_skills=skills,
    )
    for _ in range(40):
        await asyncio.sleep(0.01)
        snapshot = manager.page(started.state.id, 1, 25)
        assert snapshot is not None
        if snapshot.is_complete:
            break
    final = manager.page(started.state.id, 1, 25)
    assert final is not None
    assert [item.provider_job_id for item in final.items] == ["a-2", "a-1"]
    for item in final.items:
        assert item.relevance_score > 0
        if item.provider_job_id == "a-1":
            assert item.matched_skills == ["Python"]
    await manager.close()


@pytest.fixture
def relevance_api_client(db_session: Session) -> SearchApiClient:
    provider = FakeProvider(
        total_pages=1,
        items_per_page=2,
        delay=0.01,
        item_factory=lambda page, index: make_job_result(
            provider_job_id=f"job-{index}",
            title=f"Python Role {index}",
            description="django backend",
        ),
    )
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


def test_search_api_returns_relevance_fields(
    relevance_api_client: SearchApiClient,
) -> None:
    client, _manager = relevance_api_client
    profile = client.post(
        "/profiles",
        json={
            "display_name": "Ranker",
            "skills": [{"label": "Python"}],
            "preferences": {"query": "python", "sort": "relevance"},
        },
    )
    assert profile.status_code == 201
    profile_id = profile.json()["id"]
    created = client.post(
        "/searches",
        json={
            "profile_id": profile_id,
            "filters": {"query": "python", "sort": "relevance"},
        },
    )
    assert created.status_code == 202
    search_id = created.json()["search_id"]
    final = None
    for _ in range(50):
        response = client.get(f"/searches/{search_id}?profile_id={profile_id}")
        assert response.status_code == 200
        final = response.json()
        if final["is_complete"]:
            break
    assert final is not None
    assert final["items"]
    for item in final["items"]:
        assert "relevance_score" in item
        assert "matched_skills" in item
        assert item["matched_skills"] == ["Python"]
