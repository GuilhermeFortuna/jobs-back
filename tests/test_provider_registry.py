from __future__ import annotations

import pytest

from jobs_back.config import Settings
from jobs_back.providers.registry import (
    KNOWN_KEYS,
    build_providers,
    enabled_provider_count,
    resolve_all_provider_states,
    resolve_provider_state,
)


def test_empty_config_enables_keyless_defaults_without_adzuna() -> None:
    settings = Settings(provider_config_json="{}")
    providers = build_providers(settings)
    assert [provider.key for provider in providers] == [
        "himalayas",
        "remoteok",
        "jobicy",
    ]
    assert enabled_provider_count(settings) == 3
    states = resolve_all_provider_states(settings)
    assert states["adzuna"] == "unconfigured"


def test_adzuna_enabled_when_credentials_present() -> None:
    settings = Settings(
        adzuna_app_id="app-id",
        adzuna_app_key="app-key",
    )
    providers = build_providers(settings)
    assert [provider.key for provider in providers] == list(KNOWN_KEYS)
    assert enabled_provider_count(settings) == 4
    assert resolve_provider_state("adzuna", settings) == "enabled"


def test_adzuna_unconfigured_with_partial_credentials() -> None:
    settings = Settings(adzuna_app_id="app-id")
    assert resolve_provider_state("adzuna", settings) == "unconfigured"
    assert "adzuna" not in [provider.key for provider in build_providers(settings)]


def test_adzuna_disabled_by_configuration() -> None:
    settings = Settings(
        provider_config_json='{"adzuna": {"enabled": false}}',
        adzuna_app_id="app-id",
        adzuna_app_key="app-key",
    )
    assert resolve_provider_state("adzuna", settings) == "disabled"
    assert "adzuna" not in [provider.key for provider in build_providers(settings)]


def test_disable_provider_by_config() -> None:
    settings = Settings(provider_config_json='{"jobicy": {"enabled": false}}')
    providers = build_providers(settings)
    assert [provider.key for provider in providers] == ["himalayas", "remoteok"]


def test_unknown_key_rejected() -> None:
    settings = Settings(provider_config_json='{"bogus": {"enabled": true}}')
    with pytest.raises(ValueError, match="Unknown provider key.*bogus"):
        build_providers(settings)


def test_malformed_entry_rejected() -> None:
    with pytest.raises(ValueError, match="must be an object"):
        _ = Settings(provider_config_json='{"himalayas": "nope"}').provider_config


def test_empty_enabled_set_rejected() -> None:
    with pytest.raises(ValueError, match="enables no providers"):
        build_providers(
            Settings(
                provider_config_json='{"himalayas": {"enabled": false}, '
                '"remoteok": {"enabled": false}, "jobicy": {"enabled": false}, '
                '"adzuna": {"enabled": false}}'
            )
        )


def test_adapter_options_passed_through() -> None:
    settings = Settings(
        provider_config_json=(
            '{"remoteok": {"enabled": true, "options": {"batch_size": 25}}}'
        )
    )
    providers = build_providers(settings)
    remoteok = next(p for p in providers if p.key == "remoteok")
    assert remoteok._batch_size == 25


def test_adzuna_request_budget_option_passed_through() -> None:
    settings = Settings(
        adzuna_app_id="app-id",
        adzuna_app_key="app-key",
        provider_config_json=(
            '{"adzuna": {"enabled": true, "options": {"request_budget": 12}}}'
        ),
    )
    providers = build_providers(settings)
    adzuna = next(p for p in providers if p.key == "adzuna")
    assert adzuna._request_budget == 12
