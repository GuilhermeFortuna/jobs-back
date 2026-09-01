"""Adapter registry for provider ingestion."""

from __future__ import annotations

import re
from collections.abc import Callable

from jobs_back.config import Settings
from jobs_back.ingestion.exceptions import (
    AdapterProviderMismatchError,
    UnknownProviderError,
)
from jobs_back.ingestion.protocol import ProviderAdapter

AdapterFactory = Callable[[Settings], ProviderAdapter]

_REGISTRY: dict[str, AdapterFactory] = {}
_PROVIDER_KEY_RE = re.compile(r"^[a-z0-9_-]+$")


def _validate_provider_key(provider_key: str) -> None:
    if (
        not isinstance(provider_key, str)
        or not provider_key
        or len(provider_key) > 64
        or not _PROVIDER_KEY_RE.fullmatch(provider_key)
    ):
        raise ValueError(
            "provider_key must be 1-64 lowercase letters, digits, _, or -",
        )


def register(provider_key: str, factory: AdapterFactory) -> None:
    """Register an adapter factory for a provider key."""
    _validate_provider_key(provider_key)
    if provider_key in _REGISTRY:
        msg = f"Duplicate provider registration: {provider_key!r}"
        raise ValueError(msg)
    _REGISTRY[provider_key] = factory


def unregister(provider_key: str) -> None:
    """Remove a provider registration (primarily for tests)."""
    _REGISTRY.pop(provider_key, None)


def clear_registry() -> None:
    """Remove all registrations (primarily for tests)."""
    _REGISTRY.clear()


def registered_keys() -> frozenset[str]:
    return frozenset(_REGISTRY)


def resolve(provider_key: str, settings: Settings) -> ProviderAdapter:
    """Instantiate the adapter for a provider key."""
    factory = _REGISTRY.get(provider_key)
    if factory is None:
        raise UnknownProviderError(
            f"Unknown provider: {provider_key!r}",
        )
    adapter = factory(settings)
    if adapter.provider_key != provider_key:
        raise AdapterProviderMismatchError(
            "Resolved adapter.provider_key does not match its registry key",
        )
    return adapter


__all__ = [
    "AdapterFactory",
    "clear_registry",
    "register",
    "registered_keys",
    "resolve",
    "unregister",
]
