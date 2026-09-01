from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Protocol

from jobs_back.schemas.discovery import JobResult, SearchFilters


@dataclass(frozen=True)
class ProviderPageBatch:
    items: list[JobResult]
    page: int
    total_pages: int
    warnings: tuple[str, ...] = field(default_factory=tuple)


class ProgressiveProvider(Protocol):
    key: str

    def pages(self, filters: SearchFilters) -> AsyncIterator[ProviderPageBatch]: ...

    async def close(self) -> None: ...
