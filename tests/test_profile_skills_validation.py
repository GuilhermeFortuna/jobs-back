"""Validation tests for profile skills."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

from jobs_back.models.profile import Profile


def test_skills_count_cap_returns_422(api_client: TestClient) -> None:
    skills = [{"label": f"skill-{index}"} for index in range(51)]
    response = api_client.post(
        "/profiles",
        json={"display_name": "Too Many Skills", "skills": skills},
    )
    assert response.status_code == 422


def test_label_length_returns_422(api_client: TestClient) -> None:
    response = api_client.post(
        "/profiles",
        json={"display_name": "Long Label", "skills": [{"label": "x" * 61}]},
    )
    assert response.status_code == 422

    response = api_client.post(
        "/profiles",
        json={"display_name": "Empty Label", "skills": [{"label": "   "}]},
    )
    assert response.status_code == 422


def test_empty_token_returns_422(api_client: TestClient) -> None:
    response = api_client.post(
        "/profiles",
        json={"display_name": "Punctuation Only", "skills": [{"label": "---"}]},
    )
    assert response.status_code == 422
    assert "empty token" in response.json()["detail"].lower()


def test_duplicate_token_returns_422_with_both_labels(
    api_client: TestClient, db_session
) -> None:
    response = api_client.post(
        "/profiles",
        json={
            "display_name": "Duplicate Skills",
            "skills": [{"label": "k8s"}, {"label": "Kubernetes"}],
        },
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "kubernetes" in detail
    assert "k8s" in detail
    assert "Kubernetes" in detail

    profiles = list(db_session.scalars(select(Profile)))
    assert not any(profile.display_name == "Duplicate Skills" for profile in profiles)


def test_client_supplied_token_is_rejected(api_client: TestClient) -> None:
    response = api_client.post(
        "/profiles",
        json={
            "display_name": "Token Injection",
            "skills": [{"label": "Python", "token": "python"}],
        },
    )
    assert response.status_code == 422


def test_patch_duplicate_skills_does_not_write(
    api_client: TestClient, db_session
) -> None:
    created = api_client.post(
        "/profiles",
        json={"display_name": "Patch Dup", "skills": [{"label": "Python"}]},
    )
    assert created.status_code == 201
    profile_id = created.json()["id"]

    response = api_client.patch(
        f"/profiles/{profile_id}",
        json={"skills": [{"label": "python"}, {"label": "Python"}]},
    )
    assert response.status_code == 422

    fetched = api_client.get(f"/profiles/{profile_id}")
    assert fetched.json()["skills"] == [{"label": "Python", "token": "python"}]


def test_unknown_profile_skills_patch_returns_404(api_client: TestClient) -> None:
    missing = uuid.uuid4()
    response = api_client.patch(
        f"/profiles/{missing}",
        json={"skills": [{"label": "Python"}]},
    )
    assert response.status_code == 404
