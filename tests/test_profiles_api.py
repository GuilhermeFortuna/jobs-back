"""PostgreSQL integration tests for trusted profiles API."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


def test_create_list_get_patch_profile(api_client: TestClient) -> None:
    create = api_client.post(
        "/profiles",
        json={
            "display_name": "  Alice  ",
            "preferences": {"query": "python", "sort": "newest"},
        },
    )
    assert create.status_code == 201
    profile = create.json()
    assert profile["display_name"] == "Alice"
    assert profile["preferences"]["query"] == "python"
    profile_id = profile["id"]

    listed = api_client.get("/profiles")
    assert listed.status_code == 200
    assert any(item["id"] == profile_id for item in listed.json())

    fetched = api_client.get(f"/profiles/{profile_id}")
    assert fetched.status_code == 200
    assert fetched.json()["display_name"] == "Alice"

    patched = api_client.patch(
        f"/profiles/{profile_id}",
        json={"display_name": "Alice B", "preferences": {"query": "django"}},
    )
    assert patched.status_code == 200
    body = patched.json()
    assert body["display_name"] == "Alice B"
    assert body["preferences"]["query"] == "django"
    assert body["updated_at"] >= profile["updated_at"]


def test_duplicate_profile_name_returns_409(api_client: TestClient) -> None:
    first = api_client.post("/profiles", json={"display_name": "Bob"})
    assert first.status_code == 201
    second = api_client.post("/profiles", json={"display_name": "Bob"})
    assert second.status_code == 409


def test_invalid_preferences_return_422(api_client: TestClient) -> None:
    response = api_client.post(
        "/profiles",
        json={"display_name": "Carol", "preferences": {"sort": "invalid"}},
    )
    assert response.status_code == 422


def test_unknown_profile_returns_404(api_client: TestClient) -> None:
    missing = uuid.uuid4()
    assert api_client.get(f"/profiles/{missing}").status_code == 404
    assert (
        api_client.patch(f"/profiles/{missing}", json={"display_name": "X"}).status_code
        == 404
    )
