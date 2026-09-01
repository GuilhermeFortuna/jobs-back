from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable, Sequence

from jobs_back.providers.protocol import ProgressiveProvider, ProviderPageBatch
from jobs_back.schemas.discovery import JobResult, SearchFilters
from jobs_back.search.live import LiveSearchManager
from tests.helpers.discovery import make_job_result


class FakeProvider:
    key = "fake"

    def __init__(
        self,
        *,
        key: str = "fake",
        total_pages: int = 3,
        items_per_page: int = 2,
        delay: float = 0,
        fail_pages: frozenset[int] = frozenset(),
        fail_entirely: bool = False,
        completion_order: list[int] | None = None,
        item_factory: Callable[[int, int], JobResult] | None = None,
        revise_total_on_page: dict[int, int] | None = None,
    ) -> None:
        self.key = key
        self.total_pages = total_pages
        self.items_per_page = items_per_page
        self.delay = delay
        self.fail_pages = fail_pages
        self.fail_entirely = fail_entirely
        self.completion_order = completion_order
        self.item_factory = item_factory or self._default_item
        self.revise_total_on_page = revise_total_on_page or {}
        self.closed = False

    def _default_item(self, page: int, index: int) -> JobResult:
        return make_job_result(
            provider=self.key,
            provider_job_id=f"{self.key}-{page}-{index}",
            title=f"Role {page}-{index}",
            posted_at=None,
        )

    async def pages(self, filters: SearchFilters) -> AsyncIterator[ProviderPageBatch]:
        del filters
        if self.fail_entirely:
            raise RuntimeError("provider unavailable")
        pages = self.completion_order or list(range(1, self.total_pages + 1))
        for page in pages:
            if self.delay:
                await asyncio.sleep(self.delay)
            total_pages = self.revise_total_on_page.get(page, self.total_pages)
            if page in self.fail_pages:
                yield ProviderPageBatch(
                    items=[],
                    page=page,
                    total_pages=total_pages,
                    warnings=(f"page {page} failed",),
                )
                continue
            items = [
                self.item_factory(page, index) for index in range(self.items_per_page)
            ]
            yield ProviderPageBatch(
                items=items,
                page=page,
                total_pages=total_pages,
            )

    async def close(self) -> None:
        self.closed = True


def multi_provider_manager(
    providers: Sequence[ProgressiveProvider],
    **manager_kwargs: object,
) -> LiveSearchManager:
    return LiveSearchManager(providers=providers, **manager_kwargs)
