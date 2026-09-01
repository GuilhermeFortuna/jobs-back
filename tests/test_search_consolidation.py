"""Tests for in-memory cross-provider duplicate consolidation."""

from __future__ import annotations

import asyncio
from decimal import Decimal
from uuid import uuid4

import pytest

from jobs_back.schemas.discovery import SearchFilters
from jobs_back.search.consolidation import merge_results
from jobs_back.search.live import LiveSearchManager
from tests.helpers.discovery import make_job_result
from tests.helpers.fake_provider import FakeProvider, multi_provider_manager


def test_merge_results_keeps_richer_canonical_and_alternates() -> None:
    rich = make_job_result(
        provider="himalayas",
        provider_job_id="h-1",
        description="A" * 200,
        salary_max_annual=Decimal("200000"),
    )
    sparse = make_job_result(
        provider="remoteok",
        provider_job_id="r-1",
        description="Short",
        salary_max_annual=None,
        job_url="https://remoteok.com/jobs/1",
        apply_url="https://remoteok.com/jobs/1/apply",
    )
    merged = merge_results(rich, sparse)
    assert merged.provider == "himalayas"
    assert len(merged.alternate_sources) == 1
    assert merged.alternate_sources[0].provider == "remoteok"


@pytest.mark.asyncio
async def test_duplicates_consolidate_into_one_result() -> None:
    duplicate = make_job_result(
        provider="himalayas",
        provider_job_id="h-1",
        company="Acme Corp, Inc.",
        title="Senior Python Developer [Remote]",
    )
    twin = make_job_result(
        provider="remoteok",
        provider_job_id="r-1",
        company="ACME CORP",
        title="Senior Python Developer",
        job_url="https://remoteok.com/jobs/1",
        apply_url="https://remoteok.com/jobs/1/apply",
    )
    providers = [
        FakeProvider(
            key="himalayas",
            total_pages=1,
            items_per_page=1,
            item_factory=lambda _p, _i: duplicate,
        ),
        FakeProvider(
            key="remoteok",
            total_pages=1,
            items_per_page=1,
            item_factory=lambda _p, _i: twin,
        ),
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
    assert final.total == 1
    assert len(final.items) == 1
    item = final.items[0]
    assert item.alternate_sources
    providers_seen = {item.provider, *(s.provider for s in item.alternate_sources)}
    assert providers_seen == {"himalayas", "remoteok"}
    await manager.close()


@pytest.mark.asyncio
async def test_resolve_job_matches_alternate_source_identity() -> None:
    canonical = make_job_result(provider="himalayas", provider_job_id="h-1")
    alternate = make_job_result(
        provider="remoteok",
        provider_job_id="r-1",
        job_url="https://remoteok.com/jobs/1",
        apply_url="https://remoteok.com/jobs/1/apply",
    )
    merged = merge_results(canonical, alternate)
    manager = LiveSearchManager(provider=FakeProvider(total_pages=1, items_per_page=0))
    search_id = manager.start(uuid4(), SearchFilters()).state.id
    state = manager.states[search_id]
    manager._consolidate_items(state, [merged])
    resolved = manager.resolve_job(
        search_id,
        state.profile_id,
        "remoteok",
        "r-1",
    )
    assert resolved.provider == "himalayas"
    assert any(source.provider == "remoteok" for source in resolved.alternate_sources)
    await manager.close()


@pytest.mark.asyncio
async def test_completed_total_uses_consolidated_count() -> None:
    items = [
        make_job_result(provider_job_id="unique-1", title="Engineer I"),
        make_job_result(provider_job_id="unique-2", title="Engineer II"),
        make_job_result(
            provider="remoteok",
            provider_job_id="dup-1",
            company="Acme Corp",
            title="Backend Engineer",
            job_url="https://remoteok.com/jobs/1",
        ),
        make_job_result(
            provider="jobicy",
            provider_job_id="dup-2",
            company="Acme Corp, Inc.",
            title="Backend Engineer",
            job_url="https://jobicy.com/jobs/1",
        ),
    ]
    provider = FakeProvider(
        total_pages=1,
        items_per_page=len(items),
        item_factory=lambda _page, index: items[index],
    )
    manager = LiveSearchManager(provider=provider)
    started = manager.start(uuid4(), SearchFilters())
    for _ in range(60):
        await asyncio.sleep(0.01)
        snapshot = manager.page(started.state.id, 1, 25)
        assert snapshot is not None
        if snapshot.is_complete:
            break
    final = manager.page(started.state.id, 1, 25)
    assert final is not None
    assert final.total == 3
    await manager.close()
