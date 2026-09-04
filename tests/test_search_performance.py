from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from jobs_back.config import Settings
from jobs_back.schemas.discovery import SearchFilters
from jobs_back.search.live import LiveSearchManager
from tests.helpers.discovery import make_job_result


def _synthetic_items(count: int, *, with_duplicates: bool = False) -> list:
    base = datetime(2024, 1, 1, tzinfo=UTC)
    items = []
    for index in range(count):
        primary = make_job_result(
            provider_job_id=f"job-{index}",
            title=f"Role {index}",
            salary_max_annual=Decimal(index),
            posted_at=base + timedelta(days=index % 365),
        )
        items.append(primary)
        if with_duplicates:
            items.append(
                make_job_result(
                    provider="remoteok",
                    provider_job_id=f"dup-{index}",
                    title=primary.title,
                    company=f"{primary.company}, Inc.",
                    eligible_country_codes=primary.eligible_country_codes,
                    location_text=primary.location_text,
                    salary_max_annual=primary.salary_max_annual,
                    posted_at=primary.posted_at,
                    job_url=f"https://remoteok.com/jobs/{index}",
                )
            )
    return items


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


@pytest.mark.benchmark
@pytest.mark.asyncio
async def test_consolidation_scales_sub_quadratically_with_duplicates() -> None:
    manager = LiveSearchManager(
        provider=StaticProvider([]),
        settings=Settings(search_max_candidates_per_search=10_000),
    )
    filters = SearchFilters(sort="salary")

    async def run(count: int) -> float:
        provider = StaticProvider(_synthetic_items(count, with_duplicates=True))
        manager.providers = [provider]
        state = manager.start(uuid4(), filters).state
        started = time.perf_counter()
        await manager._populate(state, (uuid4(), "key"))
        elapsed = time.perf_counter() - started
        assert state.status == "complete"
        assert len(state.items) == count
        return elapsed

    small = await run(500)
    large = await run(5_000)
    await manager.close()
    assert large / small <= 20


@pytest.mark.benchmark
@pytest.mark.asyncio
async def test_relevance_filter_and_sort_scales_sub_quadratically() -> None:
    skills = [{"label": f"skill-{index}", "token": "python"} for index in range(10)]
    filters = SearchFilters(query="python", sort="relevance")

    async def run(count: int) -> float:
        base = datetime(2024, 1, 1, tzinfo=UTC)
        items = [
            make_job_result(
                provider_job_id=f"job-{index}",
                title=f"Python Role {index}",
                description=f"Backend services {index}",
                posted_at=base + timedelta(days=index % 365),
            )
            for index in range(count)
        ]
        provider = StaticProvider(items)
        manager = LiveSearchManager(
            provider=provider,
            settings=Settings(search_max_candidates_per_search=10_000),
        )
        state = manager.start(uuid4(), filters, profile_skills=skills).state
        started = time.perf_counter()
        await manager._populate(state, (uuid4(), "key"))
        elapsed = time.perf_counter() - started
        assert state.status == "complete"
        assert len(state.items) == count
        assert all(item.relevance_score > 0 for item in state.items)
        await manager.close()
        return elapsed

    small = await run(1_000)
    large = await run(10_000)
    assert large / small <= 15
