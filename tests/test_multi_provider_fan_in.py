from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from jobs_back.schemas.discovery import SearchFilters
from jobs_back.search.live import LiveSearchManager
from tests.helpers.fake_provider import FakeProvider, multi_provider_manager


@pytest.mark.asyncio
async def test_multi_provider_merges_results() -> None:
    providers = [
        FakeProvider(key="alpha", total_pages=2, items_per_page=1),
        FakeProvider(key="beta", total_pages=1, items_per_page=2),
    ]
    manager = multi_provider_manager(providers)
    started = manager.start(uuid4(), SearchFilters())
    for _ in range(60):
        await asyncio.sleep(0.01)
        snapshot = manager.page(started.state.id, 1, 25)
        assert snapshot is not None
        if snapshot.is_complete:
            break
    final = manager.page(started.state.id, 1, 25)
    assert final is not None
    assert final.status == "complete"
    assert len(final.items) == 3
    assert final.total == 3
    assert final.checked_count == 4
    assert {item.provider for item in final.items} == {"alpha", "beta"}
    assert len(final.providers) == 2
    await manager.close()


@pytest.mark.asyncio
async def test_aggregate_progress_is_monotonic_with_uneven_providers() -> None:
    providers = [
        FakeProvider(key="slow", total_pages=4, items_per_page=1, delay=0.02),
        FakeProvider(key="bulk", total_pages=1, items_per_page=3),
    ]
    manager = multi_provider_manager(providers)
    started = manager.start(uuid4(), SearchFilters())
    seen: list[float] = []
    for _ in range(80):
        await asyncio.sleep(0.01)
        snapshot = manager.page(started.state.id, 1, 25)
        assert snapshot is not None
        seen.append(snapshot.progress)
        if snapshot.is_complete:
            break
    assert seen == sorted(seen)
    assert seen[-1] == 1
    await manager.close()


@pytest.mark.asyncio
async def test_progress_monotonic_when_total_pages_revised_upward() -> None:
    provider = FakeProvider(
        total_pages=2,
        items_per_page=1,
        revise_total_on_page={2: 4},
    )
    manager = LiveSearchManager(provider=provider)
    started = manager.start(uuid4(), SearchFilters())
    seen: list[float] = []
    for _ in range(60):
        await asyncio.sleep(0.01)
        snapshot = manager.page(started.state.id, 1, 25)
        assert snapshot is not None
        seen.append(snapshot.progress)
        if snapshot.is_complete:
            break
    assert seen == sorted(seen)
    await manager.close()


@pytest.mark.asyncio
async def test_total_null_until_all_providers_finish() -> None:
    providers = [
        FakeProvider(key="fast", total_pages=1, items_per_page=1),
        FakeProvider(key="slow", total_pages=3, items_per_page=1, delay=0.03),
    ]
    manager = multi_provider_manager(providers)
    started = manager.start(uuid4(), SearchFilters())
    saw_loading_without_total = False
    for _ in range(80):
        await asyncio.sleep(0.01)
        snapshot = manager.page(started.state.id, 1, 25)
        assert snapshot is not None
        if snapshot.status == "loading":
            assert snapshot.total is None
            saw_loading_without_total = True
        if snapshot.is_complete:
            break
    assert saw_loading_without_total
    final = manager.page(started.state.id, 1, 25)
    assert final is not None
    assert final.total is not None
    await manager.close()
