from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from jobs_back.config import Settings
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


@pytest.mark.asyncio
async def test_filtering_to_a_disabled_provider_completes_empty() -> None:
    """No provider participating is an empty search, not a failed one."""
    manager = multi_provider_manager(
        [FakeProvider(key="himalayas", total_pages=1, items_per_page=5)],
        settings=Settings(search_state_ttl_minutes=60),
        enabled_provider_count=1,
    )
    started = manager.start(uuid4(), SearchFilters(providers=["jobicy"]))
    snapshot = None
    for _ in range(60):
        await asyncio.sleep(0.01)
        snapshot = manager.page(started.state.id, 1, 25)
        if snapshot and snapshot.status in {"complete", "failed"}:
            break

    assert snapshot is not None
    assert snapshot.status == "complete"
    assert snapshot.is_partial is False
    assert snapshot.items == []
    assert snapshot.total == 0
    assert any("jobicy" in warning.lower() for warning in snapshot.warnings)
    await manager.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("failed_key", ["remotive", "weworkremotely"])
async def test_new_provider_failure_yields_partial_complete(failed_key: str) -> None:
    providers = [
        FakeProvider(key="himalayas", total_pages=1, items_per_page=2),
        FakeProvider(key=failed_key, fail_entirely=True),
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
    assert any(f"{failed_key}:" in warning for warning in final.warnings)
    await manager.close()
