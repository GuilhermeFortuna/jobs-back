from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from jobs_back.schemas.discovery import SearchFilters
from jobs_back.search.live import LiveSearchManager
from tests.helpers.discovery import make_job_result


def _synthetic_items(count: int) -> list:
    base = datetime(2024, 1, 1, tzinfo=UTC)
    return [
        make_job_result(
            provider_job_id=f"job-{index}",
            salary_max_annual=Decimal(index),
            posted_at=base + timedelta(days=index % 365),
        )
        for index in range(count)
    ]


class StaticProvider:
    key = "static"

    def __init__(self, items: list) -> None:
        self.items = items

    async def pages(self, filters: SearchFilters):
        from jobs_back.providers.protocol import ProviderPageBatch

        del filters
        yield ProviderPageBatch(items=self.items, page=1, total_pages=1)

    async def close(self) -> None:
        return None


@pytest.mark.benchmark
@pytest.mark.asyncio
async def test_filter_and_sort_scales_sub_quadratically() -> None:
    manager = LiveSearchManager(provider=StaticProvider([]))
    filters = SearchFilters(minimum_salary=1000, sort="salary")

    async def run(count: int) -> float:
        provider = StaticProvider(_synthetic_items(count))
        manager.provider = provider
        state = manager.start(uuid4(), filters).state
        started = time.perf_counter()
        await manager._populate(state, (uuid4(), "key"))
        elapsed = time.perf_counter() - started
        assert state.status == "complete"
        assert len(state.items) < count
        return elapsed

    small = await run(10_000)
    large = await run(100_000)
    await manager.close()
    assert large / small <= 15
