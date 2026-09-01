"""Provider adapter protocol for ingestion."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from jobs_back.models.enums import SyncMode
from jobs_back.schemas.job import NormalizedJobInput


class ProviderAdapter(Protocol):
    """Contract each provider adapter must satisfy."""

    provider_key: str
    sync_mode: SyncMode

    def iter_jobs(self) -> AsyncIterator[NormalizedJobInput]: ...


__all__ = ["ProviderAdapter"]
