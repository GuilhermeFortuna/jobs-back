from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from jobs_back.config import Settings
from jobs_back.schemas.discovery import SearchFilters
from jobs_back.search.live import LiveSearchManager
from tests.helpers.fake_provider import FakeProvider


@pytest.mark.asyncio
async def test_startup_background_tasks_do_not_start_profile_searches() -> None:
    manager = LiveSearchManager(provider=FakeProvider(total_pages=1, items_per_page=1))
    manager.start_background_tasks()
    await asyncio.sleep(0)
    assert not manager.states
    await manager.close()


@pytest.mark.asyncio
async def test_shutdown_cancels_active_search() -> None:
    provider = FakeProvider(
        total_pages=5,
        items_per_page=1,
        delay=0.05,
    )
    manager = LiveSearchManager(provider=provider)
    started = manager.start(uuid4(), SearchFilters())
    await manager.close()
    snapshot = manager.page(started.state.id, 1, 25)
    assert snapshot is not None


def test_eviction_respects_ttl() -> None:
    manager = LiveSearchManager(
        provider=FakeProvider(total_pages=1, items_per_page=0),
        settings=Settings(search_state_ttl_minutes=0, search_max_states=100),
    )
    started = manager.start(uuid4(), SearchFilters())
    manager.evict_expired()
    assert started.state.id in manager.evicted


@pytest.mark.asyncio
async def test_eviction_loop_evicts_expired_states() -> None:
    manager = LiveSearchManager(
        provider=FakeProvider(total_pages=1, items_per_page=0),
        settings=Settings(
            search_state_ttl_minutes=0,
            search_eviction_interval_seconds=1,
        ),
    )
    started = manager.start(uuid4(), SearchFilters())
    manager.start_background_tasks()
    for _ in range(40):
        await asyncio.sleep(0.1)
        if started.state.id in manager.evicted:
            break
    assert started.state.id in manager.evicted
    await manager.close()
