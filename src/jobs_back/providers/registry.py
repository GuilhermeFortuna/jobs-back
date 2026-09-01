from __future__ import annotations

from typing import Any

from jobs_back.config import Settings
from jobs_back.providers.himalayas import HimalayasProvider
from jobs_back.providers.jobicy import JobicyProvider
from jobs_back.providers.protocol import ProgressiveProvider
from jobs_back.providers.remoteok import RemoteOKProvider

KNOWN_KEYS = ("himalayas", "remoteok", "jobicy")
DEFAULT_ENABLED = KNOWN_KEYS


def _coerce_int(value: Any, default: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return default


def _coerce_float(value: Any, default: float) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return default
    return default


def _factory(
    key: str,
    settings: Settings,
    options: dict[str, Any],
) -> ProgressiveProvider:
    if key == "himalayas":
        return HimalayasProvider(
            concurrency=_coerce_int(
                options.get("concurrency"),
                settings.himalayas_concurrency,
            ),
            timeout=_coerce_float(
                options.get("timeout"),
                settings.himalayas_timeout_seconds,
            ),
        )
    if key == "remoteok":
        return RemoteOKProvider(
            timeout=_coerce_float(options.get("timeout"), 20.0),
            batch_size=_coerce_int(options.get("batch_size"), 100),
        )
    if key == "jobicy":
        return JobicyProvider(
            timeout=_coerce_float(options.get("timeout"), 20.0),
        )
    msg = f"Unknown provider key: {key}"
    raise ValueError(msg)


def build_providers(settings: Settings) -> list[ProgressiveProvider]:
    configured = settings.provider_config
    if configured:
        for key in configured:
            if key not in KNOWN_KEYS:
                msg = f"Unknown provider key in PROVIDER_CONFIG_JSON: {key}"
                raise ValueError(msg)
        enabled_keys = []
        for key in KNOWN_KEYS:
            entry = configured.get(key)
            if entry is None or entry.enabled:
                enabled_keys.append(key)
    else:
        enabled_keys = list(DEFAULT_ENABLED)

    if not enabled_keys:
        msg = "PROVIDER_CONFIG_JSON enables no providers"
        raise ValueError(msg)

    providers: list[ProgressiveProvider] = []
    for key in enabled_keys:
        entry = configured.get(key)
        options = entry.options if entry else {}
        providers.append(_factory(key, settings, options))
    return providers


def enabled_provider_count(settings: Settings) -> int:
    configured = settings.provider_config
    if not configured:
        return len(DEFAULT_ENABLED)
    return sum(
        1
        for key in KNOWN_KEYS
        if configured.get(key) is None or configured[key].enabled
    )
