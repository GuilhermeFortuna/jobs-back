"""API contract for discovering which providers a search will actually use."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from jobs_back.config import get_settings
from jobs_back.main import create_app


@pytest.fixture
def client_with_provider_config(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[object, None, None]:
    def build(config_json: str) -> TestClient:
        monkeypatch.setenv("PROVIDER_CONFIG_JSON", config_json)
        get_settings.cache_clear()
        return TestClient(create_app())

    yield build
    get_settings.cache_clear()


def test_lists_every_enabled_provider_with_a_display_name(
    client_with_provider_config,
) -> None:
    with client_with_provider_config("{}") as client:
        response = client.get("/providers")

    assert response.status_code == 200
    body = response.json()
    assert [entry["key"] for entry in body] == ["himalayas", "remoteok", "jobicy"]
    assert {entry["display_name"] for entry in body} == {
        "Himalayas",
        "Remote OK",
        "Jobicy",
    }


def test_omits_a_provider_disabled_by_configuration(
    client_with_provider_config,
) -> None:
    with client_with_provider_config('{"jobicy": {"enabled": false}}') as client:
        response = client.get("/providers")

    assert response.status_code == 200
    keys = [entry["key"] for entry in response.json()]
    assert keys == ["himalayas", "remoteok"]
    assert "jobicy" not in keys


def test_reports_exactly_what_the_search_manager_will_query(
    client_with_provider_config,
) -> None:
    """The endpoint must reflect live adapters, not configuration intent."""
    with client_with_provider_config('{"remoteok": {"enabled": false}}') as client:
        keys = [entry["key"] for entry in client.get("/providers").json()]
        manager_keys = [
            provider.key for provider in client.app.state.search_manager.providers
        ]

    assert keys == manager_keys
