from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

import pytest

from jobs_back.config import (
    BASELINE_MAX_ITEMS,
    BASELINE_MAX_STATES,
    OBSERVED_ITEM_BYTES,
    Settings,
)
from jobs_back.schemas.discovery import JobResult, SearchFilters
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


def test_documented_item_footprint_matches_measurement() -> None:
    """The documented footprint must track the recorded fixtures, not an assumption."""
    measured = [
        _serialized_item_size("remoteok"),
        _serialized_item_size("jobicy"),
    ]
    for observed in measured:
        assert 0.5 * OBSERVED_ITEM_BYTES <= observed <= 2 * OBSERVED_ITEM_BYTES, (
            f"OBSERVED_ITEM_BYTES={OBSERVED_ITEM_BYTES} no longer reflects the "
            f"measured footprint {observed}"
        )


def test_single_provider_budget_matches_je005_baseline() -> None:
    """Enabling one provider must not shrink the JE-005 budget (JE-007 AC 9)."""
    settings = Settings()
    assert settings.effective_search_max_items(1) == BASELINE_MAX_ITEMS
    assert settings.effective_search_max_states(1) == BASELINE_MAX_STATES


def test_item_budget_grows_with_fan_in_volume() -> None:
    """Fan-in multiplies retained items, so the budget must grow with it."""
    settings = Settings()
    single = settings.effective_search_max_items(1)
    triple = settings.effective_search_max_items(3)
    assert triple >= 3 * single


def test_explicit_budget_overrides_are_respected() -> None:
    settings = Settings(search_max_items=5_000, search_max_states=7)
    assert settings.effective_search_max_items(3) == 5_000
    assert settings.effective_search_max_states(3) == 7


def test_unconfigured_adzuna_does_not_inflate_budget() -> None:
    from jobs_back.providers.registry import enabled_provider_count

    settings = Settings(provider_config_json="{}")
    assert enabled_provider_count(settings) == 5
    assert settings.effective_search_max_items(enabled_provider_count(settings)) == (
        settings.effective_search_max_items(5)
    )


def test_item_budget_scales_with_five_enabled_providers() -> None:
    settings = Settings()
    assert settings.effective_search_max_items(5) == BASELINE_MAX_ITEMS * 5


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


@pytest.mark.asyncio
async def test_fan_in_does_not_shrink_warm_capacity() -> None:
    """Warm indexes must survive fan-in volume alone (JE-007 AC 8)."""

    def distinct_items(key: str) -> Callable[[int, int], JobResult]:
        # Distinct roles per provider, so fan-in genuinely multiplies retained
        # items instead of consolidating back down to one provider's worth.
        def factory(page: int, index: int) -> JobResult:
            return make_job_result(
                provider=key,
                provider_job_id=f"{key}-{page}-{index}",
                title=f"{key} Role {page}-{index}",
                company=f"{key} Company {index}",
                posted_at=None,
            )

        return factory

    async def surviving_warm_searches(keys: list[str]) -> int:
        providers = [
            FakeProvider(
                key=key,
                total_pages=1,
                items_per_page=300,
                item_factory=distinct_items(key),
            )
            for key in keys
        ]
        manager = multi_provider_manager(
            providers,
            settings=Settings(search_state_ttl_minutes=60),
            enabled_provider_count=len(keys),
        )
        ids = []
        for _ in range(40):
            started = manager.start(uuid4(), SearchFilters())
            for _ in range(200):
                await asyncio.sleep(0.002)
                snapshot = manager.page(started.state.id, 1, 25)
                if snapshot and snapshot.is_complete:
                    break
            ids.append(started.state.id)
        manager.evict_expired()
        survivors = sum(1 for search_id in ids if search_id in manager.states)
        await manager.close()
        return survivors

    single = await surviving_warm_searches(["himalayas"])
    fan_in = await surviving_warm_searches(["himalayas", "remoteok", "jobicy"])
    assert single == 40
    assert fan_in == single
