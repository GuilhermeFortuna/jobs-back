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
            "skills": [{"label": "  Node.js  "}, {"label": "PostgreSQL"}],
        },
    )
    assert create.status_code == 201
    profile = create.json()
    assert profile["display_name"] == "Alice"
    assert profile["preferences"]["query"] == "python"
    assert profile["skills"] == [
        {"label": "Node.js", "token": "nodejs"},
        {"label": "PostgreSQL", "token": "postgresql"},
    ]
    profile_id = profile["id"]

    listed = api_client.get("/profiles")
    assert listed.status_code == 200
    listed_profile = next(item for item in listed.json() if item["id"] == profile_id)
    assert listed_profile["skills"] == profile["skills"]

    fetched = api_client.get(f"/profiles/{profile_id}")
    assert fetched.status_code == 200
    assert fetched.json()["skills"] == profile["skills"]

    patched = api_client.patch(
        f"/profiles/{profile_id}",
        json={
            "display_name": "Alice B",
            "preferences": {"query": "django"},
            "skills": [{"label": "Django"}, {"label": "Python"}],
        },
    )
    assert patched.status_code == 200
    body = patched.json()
    assert body["display_name"] == "Alice B"
    assert body["preferences"]["query"] == "django"
    assert body["skills"] == [
        {"label": "Django", "token": "django"},
        {"label": "Python", "token": "python"},
    ]
    assert body["updated_at"] >= profile["updated_at"]


def test_profile_defaults_to_empty_skills(api_client: TestClient) -> None:
    create = api_client.post("/profiles", json={"display_name": "No Skills"})
    assert create.status_code == 201
    assert create.json()["skills"] == []


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
