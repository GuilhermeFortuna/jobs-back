"""Tests for the ingestion adapter registry."""

from __future__ import annotations

import pytest

from jobs_back.config import Settings
from jobs_back.ingestion.exceptions import (
    AdapterConfigurationError,
    AdapterProviderMismatchError,
    UnknownProviderError,
)
from jobs_back.ingestion.registry import (
    clear_registry,
    register,
    resolve,
    unregister,
)
from jobs_back.models.enums import SyncMode
from tests.helpers.fake_adapters import FakeAdapter, register_fake_adapter


@pytest.fixture(autouse=True)
def _clean_registry() -> None:
    clear_registry()
    yield
    clear_registry()


def test_resolve_unknown_provider_raises() -> None:
    settings = Settings()
    with pytest.raises(UnknownProviderError):
        resolve("missing", settings)


def test_duplicate_registration_rejected() -> None:
    def factory(_: Settings) -> FakeAdapter:
        return FakeAdapter(provider_key="dup", sync_mode=SyncMode.FULL_SNAPSHOT)

    register("dup", factory)
    with pytest.raises(ValueError, match="Duplicate provider registration"):
        register("dup", factory)


@pytest.mark.parametrize("provider_key", ["", "UPPER", "has space", "x" * 65])
def test_invalid_registration_key_rejected(provider_key: str) -> None:
    def factory(_: Settings) -> FakeAdapter:
        return FakeAdapter(provider_key=provider_key, sync_mode=SyncMode.FULL_SNAPSHOT)

    with pytest.raises(ValueError, match="provider_key"):
        register(provider_key, factory)


def test_resolve_returns_adapter_from_factory() -> None:
    register_fake_adapter("fake", sync_mode=SyncMode.INCREMENTAL)
    adapter = resolve("fake", Settings())
    assert adapter.provider_key == "fake"
    assert adapter.sync_mode == SyncMode.INCREMENTAL


def test_resolve_rejects_adapter_with_different_provider_key() -> None:
    def factory(_: Settings) -> FakeAdapter:
        return FakeAdapter(provider_key="other", sync_mode=SyncMode.FULL_SNAPSHOT)

    register("expected", factory)
    with pytest.raises(AdapterProviderMismatchError):
        resolve("expected", Settings())


def test_factory_receives_settings() -> None:
    register_fake_adapter(
        "configured",
        require_config_key="api_key",
    )
    settings = Settings(provider_config_json='{"configured": {"api_key": "x"}}')
    adapter = resolve("configured", settings)
    assert adapter.provider_key == "configured"


def test_factory_raises_configuration_error() -> None:
    register_fake_adapter(
        "configured",
        require_config_key="api_key",
    )
    with pytest.raises(AdapterConfigurationError):
        resolve("configured", Settings())


def test_unregister_removes_provider() -> None:
    register_fake_adapter("temp")
    unregister("temp")
    with pytest.raises(UnknownProviderError):
        resolve("temp", Settings())
