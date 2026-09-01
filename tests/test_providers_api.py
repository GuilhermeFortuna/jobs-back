"""API contract for discovering which providers a search will actually use."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from jobs_back.config import get_settings
from jobs_back.main import create_app
from jobs_back.providers.registry import KNOWN_KEYS


@pytest.fixture
def client_with_provider_config(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[object, None, None]:
    def build(config_json: str, **env: str) -> TestClient:
        monkeypatch.setenv("PROVIDER_CONFIG_JSON", config_json)
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        get_settings.cache_clear()
        return TestClient(create_app())

    yield build
    get_settings.cache_clear()


def test_lists_every_known_provider_with_state(
    client_with_provider_config,
) -> None:
    with client_with_provider_config("{}") as client:
        response = client.get("/providers")

    assert response.status_code == 200
    body = response.json()
    assert [entry["key"] for entry in body] == list(KNOWN_KEYS)
    assert {entry["display_name"] for entry in body} == {
        "Himalayas",
        "Remote OK",
        "Jobicy",
        "Adzuna",
    }
    adzuna = next(entry for entry in body if entry["key"] == "adzuna")
    assert adzuna["state"] == "unconfigured"
    enabled = [entry for entry in body if entry["state"] == "enabled"]
    assert [entry["key"] for entry in enabled] == ["himalayas", "remoteok", "jobicy"]


def test_disabled_provider_reported_but_not_in_manager(
    client_with_provider_config,
) -> None:
    with client_with_provider_config('{"jobicy": {"enabled": false}}') as client:
        response = client.get("/providers")

    assert response.status_code == 200
    body = response.json()
    jobicy = next(entry for entry in body if entry["key"] == "jobicy")
    assert jobicy["state"] == "disabled"
    manager_keys = [
        provider.key for provider in client.app.state.search_manager.providers
    ]
    assert manager_keys == ["himalayas", "remoteok"]
    assert "jobicy" not in manager_keys


def test_adzuna_enabled_when_credentials_present(
    client_with_provider_config,
) -> None:
    with client_with_provider_config(
        "{}",
        ADZUNA_APP_ID="app-id",
        ADZUNA_APP_KEY="app-key",
    ) as client:
        body = client.get("/providers").json()
        adzuna = next(entry for entry in body if entry["key"] == "adzuna")
        assert adzuna["state"] == "enabled"
        manager_keys = [
            provider.key for provider in client.app.state.search_manager.providers
        ]
        assert "adzuna" in manager_keys


def test_reports_exactly_what_the_search_manager_will_query_for_enabled(
    client_with_provider_config,
) -> None:
    """Enabled providers in the API must match live adapters."""
    with client_with_provider_config('{"remoteok": {"enabled": false}}') as client:
        body = client.get("/providers").json()
        enabled_keys = [entry["key"] for entry in body if entry["state"] == "enabled"]
        manager_keys = [
            provider.key for provider in client.app.state.search_manager.providers
        ]

    assert enabled_keys == manager_keys
