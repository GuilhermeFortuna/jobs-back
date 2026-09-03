"""PostgreSQL advisory lock helpers for provider-scoped sync runs."""

from __future__ import annotations

import hashlib
from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine


def provider_lock_key(provider_key: str) -> int:
    """Derive a signed 64-bit advisory lock key from a provider key."""
    digest = hashlib.sha256(provider_key.encode()).digest()[:8]
    return int.from_bytes(digest, "big", signed=True)


@contextmanager
def provider_advisory_lock(
    engine: Engine,
    provider_key: str,
) -> Generator[Connection, None, None]:
    """Acquire a non-blocking advisory lock for the provider, held until release."""
    lock_key = provider_lock_key(provider_key)
    connection = engine.connect()
    acquired = connection.execute(
        text("SELECT pg_try_advisory_lock(:key)"),
        {"key": lock_key},
    ).scalar()
    if not acquired:
        connection.close()
        raise ProviderLockNotAcquired()

    try:
        yield connection
    finally:
        connection.execute(
            text("SELECT pg_advisory_unlock(:key)"),
            {"key": lock_key},
        )
        connection.close()


class ProviderLockNotAcquired(Exception):
    """Raised when pg_try_advisory_lock returns false."""


__all__ = [
    "ProviderLockNotAcquired",
    "provider_advisory_lock",
    "provider_lock_key",
]
