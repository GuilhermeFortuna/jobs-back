"""Search-cache invalidation when profile skills change."""

from __future__ import annotations

from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from jobs_back.schemas.discovery import SearchFilters
from jobs_back.search.live import LiveSearchManager, SearchState


def test_skills_change_discards_only_owning_profile_searches(
    api_client_with_search: tuple[TestClient, LiveSearchManager],
) -> None:
    client, manager = api_client_with_search

    first = client.post(
        "/profiles",
        json={"display_name": "Skills Owner", "skills": [{"label": "Python"}]},
    )
    second = client.post("/profiles", json={"display_name": "Other Profile"})
    assert first.status_code == 201
    assert second.status_code == 201
    owner_id = UUID(first.json()["id"])
    other_id = UUID(second.json()["id"])

    owner_search_id = uuid4()
    other_search_id = uuid4()
    manager.states[owner_search_id] = SearchState(
        id=owner_search_id,
        profile_id=owner_id,
        filters=SearchFilters(),
        status="complete",
        progress=1.0,
    )
    manager.latest[(owner_id, "{}")] = owner_search_id

    manager.states[other_search_id] = SearchState(
        id=other_search_id,
        profile_id=other_id,
        filters=SearchFilters(),
        status="complete",
        progress=1.0,
    )
    manager.latest[(other_id, "{}")] = other_search_id

    patched = client.patch(
        f"/profiles/{owner_id}",
        json={"skills": [{"label": "Django"}]},
    )
    assert patched.status_code == 200

    assert owner_search_id in manager.evicted
    assert owner_search_id not in manager.states
    assert other_search_id in manager.states
    assert other_search_id not in manager.evicted


def test_patch_without_skills_field_leaves_cache(
    api_client_with_search: tuple[TestClient, LiveSearchManager],
) -> None:
    client, manager = api_client_with_search

    created = client.post(
        "/profiles",
        json={"display_name": "No Skill Patch", "skills": [{"label": "Go"}]},
    )
    assert created.status_code == 201
    profile_id = UUID(created.json()["id"])

    search_id = uuid4()
    manager.states[search_id] = SearchState(
        id=search_id,
        profile_id=profile_id,
        filters=SearchFilters(),
        status="complete",
        progress=1.0,
    )
    manager.latest[(profile_id, "{}")] = search_id

    patched = client.patch(
        f"/profiles/{profile_id}",
        json={"display_name": "Renamed Profile"},
    )
    assert patched.status_code == 200
    assert search_id in manager.states
    assert search_id not in manager.evicted


def test_patch_with_identical_skills_does_not_discard(
    api_client_with_search: tuple[TestClient, LiveSearchManager],
) -> None:
    client, manager = api_client_with_search

    created = client.post(
        "/profiles",
        json={"display_name": "Same Skills", "skills": [{"label": "Rust"}]},
    )
    assert created.status_code == 201
    profile_id = UUID(created.json()["id"])

    search_id = uuid4()
    manager.states[search_id] = SearchState(
        id=search_id,
        profile_id=profile_id,
        filters=SearchFilters(),
        status="complete",
        progress=1.0,
    )
    manager.latest[(profile_id, "{}")] = search_id

    patched = client.patch(
        f"/profiles/{profile_id}",
        json={"skills": [{"label": "Rust"}]},
    )
    assert patched.status_code == 200
    assert search_id in manager.states
    assert search_id not in manager.evicted
