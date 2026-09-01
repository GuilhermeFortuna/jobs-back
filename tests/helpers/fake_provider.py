from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable

from jobs_back.providers.protocol import ProviderPageBatch
from jobs_back.schemas.discovery import JobResult, SearchFilters
from tests.helpers.discovery import make_job_result


class FakeProvider:
    key = "fake"

    def __init__(
        self,
        *,
        total_pages: int = 3,
        items_per_page: int = 2,
        delay: float = 0,
        fail_pages: frozenset[int] = frozenset(),
        completion_order: list[int] | None = None,
        item_factory: Callable[[int, int], JobResult] | None = None,
    ) -> None:
        self.total_pages = total_pages
        self.items_per_page = items_per_page
        self.delay = delay
        self.fail_pages = fail_pages
        self.completion_order = completion_order
        self.item_factory = item_factory or self._default_item
        self.closed = False

    @staticmethod
    def _default_item(page: int, index: int) -> JobResult:
        return make_job_result(
            provider_job_id=f"fake-{page}-{index}",
            title=f"Role {page}-{index}",
            posted_at=None,
        )

    async def pages(self, filters: SearchFilters) -> AsyncIterator[ProviderPageBatch]:
        del filters
        pages = self.completion_order or list(range(1, self.total_pages + 1))
        for page in pages:
            if self.delay:
                await asyncio.sleep(self.delay)
            if page in self.fail_pages:
                yield ProviderPageBatch(
                    items=[],
                    page=page,
                    total_pages=self.total_pages,
                    warnings=(f"page {page} failed",),
                )
                continue
            items = [
                self.item_factory(page, index) for index in range(self.items_per_page)
            ]
            yield ProviderPageBatch(
                items=items,
                page=page,
                total_pages=self.total_pages,
            )

    async def close(self) -> None:
        self.closed = True
