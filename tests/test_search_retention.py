from __future__ import annotations

import asyncio
import json
from pathlib import Path
from uuid import uuid4

import pytest

from jobs_back.config import Settings
from jobs_back.schemas.discovery import SearchFilters
from jobs_back.search.live import LiveSearchManager
from tests.helpers.discovery import make_job_result
from tests.helpers.fake_provider import FakeProvider, multi_provider_manager

FIXTURES = Path(__file__).parent / "fixtures"


def _serialized_item_size(provider: str) -> int:
    fixture_path = FIXTURES / provider / "sample.json"
    if provider == "remoteok":
        raw = json.loads(fixture_path.read_text())[1]
    else:
        raw = json.loads(fixture_path.read_text())["jobs"][0]
    job = make_job_result(
        provider=provider,
        provider_job_id=str(raw.get("id", "1")),
        provider_payload=raw,
    )
    return len(job.model_dump_json())


def test_measured_item_footprints_documented() -> None:
    himalayas_bytes = len(
        make_job_result(
            provider="himalayas",
            provider_payload={"guid": "x", "title": "t"},
        ).model_dump_json()
    )
    remoteok_bytes = _serialized_item_size("remoteok")
    jobicy_bytes = _serialized_item_size("jobicy")
    assert himalayas_bytes > 0
    assert remoteok_bytes > 0
    assert jobicy_bytes > 0


def test_effective_budgets_scale_with_provider_count() -> None:
    settings = Settings()
    single = settings.effective_search_max_items(1)
    triple = settings.effective_search_max_items(3)
    assert triple < single


@pytest.mark.asyncio
async def test_warm_index_not_evicted_by_fan_in_volume() -> None:
    providers = [
        FakeProvider(key="himalayas", total_pages=1, items_per_page=50),
        FakeProvider(key="remoteok", total_pages=1, items_per_page=50),
        FakeProvider(key="jobicy", total_pages=1, items_per_page=50),
    ]
    settings = Settings(search_state_ttl_minutes=60)
    manager = multi_provider_manager(
        providers,
        settings=settings,
        enabled_provider_count=3,
    )
    started = manager.start(uuid4(), SearchFilters())
    for _ in range(80):
        await asyncio.sleep(0.01)
        snapshot = manager.page(started.state.id, 1, 25)
        assert snapshot is not None
        if snapshot.is_complete:
            break
    manager.evict_expired()
    assert started.state.id not in manager.evicted
    await manager.close()


def test_loading_search_is_budget_protected() -> None:
    manager = LiveSearchManager(
        provider=FakeProvider(total_pages=5, delay=1),
        settings=Settings(search_max_states=1, search_state_ttl_minutes=60),
    )
    started = manager.start(uuid4(), SearchFilters())
    manager.evict_expired()
    assert started.state.id in manager.states


@pytest.mark.asyncio
async def test_refresh_stale_index_is_budget_protected() -> None:
    manager = LiveSearchManager(
        provider=FakeProvider(total_pages=1, items_per_page=1),
        settings=Settings(search_max_states=1, search_state_ttl_minutes=60),
    )
    profile_id = uuid4()
    filters = SearchFilters()
    first = manager.start(profile_id, filters)
    for _ in range(40):
        await asyncio.sleep(0.01)
        snapshot = manager.page(first.state.id, 1, 25)
        if snapshot and snapshot.is_complete:
            break
    refresh = manager.start(profile_id, filters, force=True)
    manager.evict_expired()
    assert first.state.id in manager.states
    assert refresh.state.id in manager.states
    await manager.close()
