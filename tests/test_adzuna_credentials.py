from __future__ import annotations

import logging
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from jobs_back.config import Settings, get_settings
from jobs_back.main import create_app
from jobs_back.providers.registry import build_providers, enabled_provider_count

SECRET_APP_ID = "super-secret-app-id-012345"
SECRET_APP_KEY = "super-secret-app-key-abcdef"


@pytest.fixture
def configured_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[Settings, None, None]:
    monkeypatch.setenv("ADZUNA_APP_ID", SECRET_APP_ID)
    monkeypatch.setenv("ADZUNA_APP_KEY", SECRET_APP_KEY)
    get_settings.cache_clear()
    yield get_settings()
    get_settings.cache_clear()


def test_credentials_never_appear_in_providers_response(
    configured_settings: Settings,
    caplog: pytest.LogCaptureFixture,
) -> None:
    del configured_settings
    with caplog.at_level(logging.DEBUG):
        with TestClient(create_app()) as client:
            response = client.get("/providers")

    assert response.status_code == 200
    serialized = response.text
    assert SECRET_APP_ID not in serialized
    assert SECRET_APP_KEY not in serialized
    assert SECRET_APP_ID not in caplog.text
    assert SECRET_APP_KEY not in caplog.text


def test_startup_succeeds_without_adzuna_credentials() -> None:
    settings = Settings(provider_config_json="{}")
    providers = build_providers(settings)
    assert enabled_provider_count(settings) == 3
    assert [provider.key for provider in providers] == [
        "himalayas",
        "remoteok",
        "jobicy",
    ]
