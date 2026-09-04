from __future__ import annotations

from typing import Any, Literal

from jobs_back.config import Settings
from jobs_back.providers.adzuna import AdzunaProvider
from jobs_back.providers.himalayas import HimalayasProvider
from jobs_back.providers.jobicy import JobicyProvider
from jobs_back.providers.protocol import ProgressiveProvider
from jobs_back.providers.remoteok import RemoteOKProvider
from jobs_back.providers.remotive import RemotiveProvider
from jobs_back.providers.weworkremotely import WeWorkRemotelyProvider

ProviderState = Literal["enabled", "unconfigured", "disabled"]

KNOWN_KEYS = ("himalayas", "remoteok", "jobicy", "adzuna", "remotive", "weworkremotely")
DEFAULT_ENABLED = KNOWN_KEYS

# Human-readable provider names. The API serves these so a new adapter needs no
# frontend change; unknown keys fall back to the key itself.
PROVIDER_DISPLAY_NAMES = {
    "himalayas": "Himalayas",
    "remoteok": "Remote OK",
    "jobicy": "Jobicy",
    "adzuna": "Adzuna",
    "remotive": "Remotive",
    "weworkremotely": "We Work Remotely",
}

# Settings attribute names required for a provider to be constructible.
PROVIDER_REQUIRED_CREDENTIALS: dict[str, tuple[str, ...]] = {
    "himalayas": (),
    "remoteok": (),
    "jobicy": (),
    "adzuna": ("adzuna_app_id", "adzuna_app_key"),
    "remotive": (),
    "weworkremotely": (),
}


def provider_display_name(key: str) -> str:
    return PROVIDER_DISPLAY_NAMES.get(key, key)


def _config_enabled(key: str, configured: dict[str, Any]) -> bool:
    if not configured:
        return True
    entry = configured.get(key)
    return entry is None or entry.enabled


def _credential_values(settings: Settings, key: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for field_name in PROVIDER_REQUIRED_CREDENTIALS.get(key, ()):
        raw = getattr(settings, field_name, "")
        values[field_name] = str(raw).strip() if raw is not None else ""
    return values


def _credentials_present(settings: Settings, key: str) -> bool:
    required = PROVIDER_REQUIRED_CREDENTIALS.get(key, ())
    if not required:
        return True
    return all(_credential_values(settings, key).values())


def resolve_provider_state(key: str, settings: Settings) -> ProviderState:
    configured = settings.provider_config
    if not _config_enabled(key, configured):
        return "disabled"
    if not _credentials_present(settings, key):
        return "unconfigured"
    return "enabled"


def resolve_all_provider_states(settings: Settings) -> dict[str, ProviderState]:
    return {key: resolve_provider_state(key, settings) for key in KNOWN_KEYS}


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


def _bounded_option(value: Any, default: int, *, minimum: int, maximum: int) -> int:
    parsed = _coerce_int(value, default)
    return parsed if minimum <= parsed <= maximum else default


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
            request_budget=_bounded_option(
                options.get("request_budget"), 10, minimum=1, maximum=50
            ),
            result_cap=_bounded_option(
                options.get("result_cap"), 200, minimum=1, maximum=1_000
            ),
        )
    if key == "remoteok":
        return RemoteOKProvider(
            timeout=_coerce_float(options.get("timeout"), 20.0),
            batch_size=_bounded_option(
                options.get("result_cap", options.get("batch_size")),
                100,
                minimum=1,
                maximum=1_000,
            ),
            max_retries=_bounded_option(
                options.get("request_budget"), 1, minimum=1, maximum=50
            ),
        )
    if key == "jobicy":
        return JobicyProvider(
            timeout=_coerce_float(options.get("timeout"), 20.0),
            result_cap=_bounded_option(
                options.get("result_cap"), 50, minimum=1, maximum=1_000
            ),
            max_retries=_bounded_option(
                options.get("request_budget"), 1, minimum=1, maximum=50
            ),
        )
    if key == "adzuna":
        creds = _credential_values(settings, key)
        return AdzunaProvider(
            app_id=creds["adzuna_app_id"],
            app_key=creds["adzuna_app_key"],
            default_country=settings.adzuna_default_country,
            concurrency=_coerce_int(
                options.get("concurrency"),
                settings.adzuna_concurrency,
            ),
            timeout=_coerce_float(
                options.get("timeout"),
                settings.adzuna_timeout_seconds,
            ),
            request_budget=_bounded_option(
                options.get("request_budget"), 10, minimum=1, maximum=50
            ),
            result_cap=_bounded_option(
                options.get("result_cap"), 200, minimum=1, maximum=1_000
            ),
        )
    if key == "remotive":
        return RemotiveProvider(
            timeout=_coerce_float(options.get("timeout"), 20.0),
            result_cap=_bounded_option(
                options.get("result_cap"), 50, minimum=1, maximum=1_000
            ),
            max_retries=_bounded_option(
                options.get("request_budget"), 1, minimum=1, maximum=50
            ),
        )
    if key == "weworkremotely":
        return WeWorkRemotelyProvider(
            timeout=_coerce_float(options.get("timeout"), 20.0),
            batch_size=_bounded_option(
                options.get("result_cap", options.get("batch_size")),
                100,
                minimum=1,
                maximum=1_000,
            ),
            feed_item_cap=_bounded_option(
                options.get("result_cap"), 100, minimum=1, maximum=1_000
            ),
            max_retries=_bounded_option(
                options.get("request_budget"), 1, minimum=1, maximum=50
            ),
        )
    msg = f"Unknown provider key: {key}"
    raise ValueError(msg)


def _config_enabled_keys(settings: Settings) -> list[str]:
    configured = settings.provider_config
    if configured:
        for key in configured:
            if key not in KNOWN_KEYS:
                msg = f"Unknown provider key in PROVIDER_CONFIG_JSON: {key}"
                raise ValueError(msg)
        enabled_keys: list[str] = []
        for key in KNOWN_KEYS:
            if _config_enabled(key, configured):
                enabled_keys.append(key)
        return enabled_keys
    return list(DEFAULT_ENABLED)


def build_providers(settings: Settings) -> list[ProgressiveProvider]:
    configured = settings.provider_config
    enabled_keys = _config_enabled_keys(settings)

    if not enabled_keys:
        msg = "PROVIDER_CONFIG_JSON enables no providers"
        raise ValueError(msg)

    providers: list[ProgressiveProvider] = []
    for key in enabled_keys:
        if resolve_provider_state(key, settings) != "enabled":
            continue
        entry = configured.get(key)
        options = entry.options if entry else {}
        providers.append(_factory(key, settings, options))
    return providers


def enabled_provider_count(settings: Settings) -> int:
    return sum(
        1 for key in KNOWN_KEYS if resolve_provider_state(key, settings) == "enabled"
    )
