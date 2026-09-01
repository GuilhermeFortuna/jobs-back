from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from jobs_back.config import Settings
from jobs_back.schemas.discovery import SearchFilters
from jobs_back.search.live import LiveSearchManager, canonical_filters, filter_key
from jobs_back.services.exceptions import SearchExpiredError
from tests.helpers.discovery import make_job_result
from tests.helpers.fake_provider import FakeProvider


@pytest.mark.asyncio
async def test_progress_is_monotonic_with_out_of_order_pages() -> None:
    provider = FakeProvider(
        total_pages=4,
        items_per_page=1,
        completion_order=[1, 4, 2, 3],
    )
    manager = LiveSearchManager(provider=provider)
    profile_id = uuid4()
    started = manager.start(profile_id, SearchFilters())
    state = started.state
    seen: list[float] = []
    for _ in range(40):
        await asyncio.sleep(0.01)
        snapshot = manager.page(state.id, 1, 25)
        assert snapshot is not None
        seen.append(snapshot.progress)
        if snapshot.is_complete:
            break
    assert seen == sorted(seen)
    assert seen[-1] == 1
    await manager.close()


@pytest.mark.asyncio
async def test_partial_page_failure_retains_results() -> None:
    provider = FakeProvider(total_pages=3, items_per_page=1, fail_pages=frozenset({2}))
    manager = LiveSearchManager(provider=provider)
    profile_id = uuid4()
    started = manager.start(profile_id, SearchFilters())
    for _ in range(40):
        await asyncio.sleep(0.01)
        snapshot = manager.page(started.state.id, 1, 25)
        assert snapshot is not None
        if snapshot.is_complete:
            break
    final = manager.page(started.state.id, 1, 25)
    assert final is not None
    assert final.status == "complete"
    assert len(final.items) == 2
    assert final.warnings
    await manager.close()


@pytest.mark.asyncio
async def test_first_page_failure_marks_search_failed() -> None:
    provider = FakeProvider(total_pages=1, fail_pages=frozenset({1}))
    manager = LiveSearchManager(provider=provider)
    started = manager.start(uuid4(), SearchFilters())
    for _ in range(40):
        await asyncio.sleep(0.01)
        snapshot = manager.page(started.state.id, 1, 25)
        assert snapshot is not None
        if snapshot.is_complete:
            break
    final = manager.page(started.state.id, 1, 25)
    assert final is not None
    assert final.status == "failed"
    assert final.items == []
    await manager.close()


@pytest.mark.asyncio
async def test_profile_scoped_indexes_do_not_cross_profiles() -> None:
    provider = FakeProvider(
        total_pages=1,
        items_per_page=1,
        item_factory=lambda page, index: make_job_result(
            provider_job_id=f"job-{page}-{index}",
            title=f"Python Role {page}-{index}",
        ),
    )
    manager = LiveSearchManager(provider=provider)
    profile_a = uuid4()
    profile_b = uuid4()
    started_a = manager.start(profile_a, SearchFilters(query="python"))
    started_b = manager.start(profile_b, SearchFilters(query="python"))
    assert started_a.state.id != started_b.state.id
    for _ in range(40):
        await asyncio.sleep(0.01)
        snapshot = manager.page(started_a.state.id, 1, 25)
        assert snapshot is not None
        if snapshot.is_complete:
            break
    snapshot_a = manager.page(started_a.state.id, 1, 25)
    assert snapshot_a is not None
    item_a = snapshot_a.items[0]
    from jobs_back.services.exceptions import NotFoundError

    with pytest.raises(NotFoundError):
        manager.resolve_job(
            started_a.state.id,
            profile_b,
            item_a.provider,
            item_a.provider_job_id,
        )
    await manager.close()


def test_canonical_filters_sort_lists() -> None:
    filters = SearchFilters(
        seniority=["lead", "senior"],
        employment_types=["contract", "full_time"],
    )
    canonical = canonical_filters(filters)
    assert canonical.seniority == ["lead", "senior"]
    assert canonical.employment_types == ["contract", "full_time"]
    reordered = SearchFilters(
        seniority=["senior", "lead"],
        employment_types=["full_time", "contract"],
    )
    assert filter_key(uuid4(), filters)[1] == filter_key(uuid4(), reordered)[1]


@pytest.mark.asyncio
async def test_stale_refresh_keeps_previous_index_readable() -> None:
    provider = FakeProvider(total_pages=1, items_per_page=2)
    manager = LiveSearchManager(provider=provider)
    profile_id = uuid4()
    filters = SearchFilters()
    first = manager.start(profile_id, filters)
    for _ in range(40):
        await asyncio.sleep(0.01)
        snapshot = manager.page(first.state.id, 1, 25)
        assert snapshot is not None
        if snapshot.is_complete:
            break
    refresh = manager.start(profile_id, filters, force=True)
    assert refresh.previous_search_id == first.state.id
    assert refresh.serving_search_id == first.state.id
    stale = manager.page(first.state.id, 1, 25)
    assert stale is not None
    assert stale.items
    await manager.close()


def test_evicted_search_returns_410() -> None:
    manager = LiveSearchManager(
        provider=FakeProvider(total_pages=1, items_per_page=0),
        settings=Settings(search_max_states=1, search_state_ttl_minutes=60),
    )
    profile_id = uuid4()
    first = manager.start(profile_id, SearchFilters())
    second = manager.start(profile_id, SearchFilters(query="other"))
    manager.evict_expired()
    with pytest.raises(SearchExpiredError):
        manager.page(first.state.id, 1, 25)
    assert manager.page(second.state.id, 1, 25) is not None


@pytest.mark.asyncio
async def test_search_without_matches_completes_instead_of_failing() -> None:
    provider = FakeProvider(total_pages=2, items_per_page=1)
    manager = LiveSearchManager(provider=provider)
    started = manager.start(uuid4(), SearchFilters(minimum_salary=10_000_000))
    for _ in range(40):
        await asyncio.sleep(0.01)
        snapshot = manager.page(started.state.id, 1, 25)
        assert snapshot is not None
        if snapshot.is_complete:
            break
    final = manager.page(started.state.id, 1, 25)
    assert final is not None
    assert final.status == "complete"
    assert final.total == 0
    assert final.warnings == []
    await manager.close()


@pytest.mark.asyncio
async def test_progress_never_exceeds_one_when_provider_overruns() -> None:
    provider = FakeProvider(
        total_pages=1, items_per_page=1, completion_order=[1, 2, 3], delay=0.03
    )
    manager = LiveSearchManager(provider=provider)
    started = manager.start(uuid4(), SearchFilters())
    seen: list[float] = []
    for _ in range(40):
        await asyncio.sleep(0.01)
        snapshot = manager.page(started.state.id, 1, 25)
        assert snapshot is not None
        seen.append(snapshot.progress)
        if snapshot.is_complete:
            break
    assert max(seen) <= 1
    await manager.close()


@pytest.mark.asyncio
async def test_failed_search_is_not_reused_within_the_reuse_window() -> None:
    provider = FakeProvider(total_pages=1, fail_pages=frozenset({1}))
    manager = LiveSearchManager(provider=provider)
    profile_id = uuid4()
    filters = SearchFilters()
    first = manager.start(profile_id, filters)
    for _ in range(40):
        await asyncio.sleep(0.01)
        snapshot = manager.page(first.state.id, 1, 25)
        assert snapshot is not None
        if snapshot.is_complete:
            break
    second = manager.start(profile_id, filters)
    assert second.state.id != first.state.id
    await manager.close()
