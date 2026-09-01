from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from jobs_back.schemas.discovery import SearchFilters
from tests.helpers.fake_provider import FakeProvider, multi_provider_manager


@pytest.mark.asyncio
async def test_one_provider_failure_yields_partial_complete() -> None:
    providers = [
        FakeProvider(key="good", total_pages=2, items_per_page=1),
        FakeProvider(key="bad", fail_entirely=True),
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
    assert final.is_partial is True
    assert len(final.items) == 2
    assert any("bad:" in warning for warning in final.warnings)
    bad = next(p for p in final.providers if p.provider == "bad")
    assert bad.status == "failed"
    await manager.close()


@pytest.mark.asyncio
async def test_all_providers_fail_marks_search_failed() -> None:
    providers = [
        FakeProvider(key="bad-a", total_pages=1, fail_pages=frozenset({1})),
        FakeProvider(key="bad-b", fail_entirely=True),
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
    assert final.status == "failed"
    assert final.is_partial is False
    assert final.items == []
    await manager.close()
