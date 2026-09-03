"""Index-side query and location filtering tests."""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from jobs_back.schemas.discovery import SearchFilters
from jobs_back.search.live import LiveSearchManager, canonical_filters, filter_key
from jobs_back.search.relevance import job_matches_location
from tests.helpers.discovery import make_job_result
from tests.helpers.fake_provider import FakeProvider


def test_location_filter_matches_normalized_text() -> None:
    job = make_job_result(location_text="Remote - US")
    assert job_matches_location(job, "remote us")
    assert not job_matches_location(job, "europe")


def test_location_filter_rejects_missing_location_text() -> None:
    job = make_job_result(location_text=None)
    assert job_matches_location(job, "")
    assert not job_matches_location(job, "remote")


def test_canonical_filters_include_location() -> None:
    filters = SearchFilters(query="python", location="Remote US")
    canonical = canonical_filters(filters)
    assert canonical.location == "Remote US"
    reordered = SearchFilters(location="Remote US", query="python")
    assert filter_key(uuid4(), filters)[1] == filter_key(uuid4(), reordered)[1]


@pytest.mark.asyncio
async def test_local_query_filter_decides_membership() -> None:
    matching = make_job_result(
        provider="alpha",
        provider_job_id="match-1",
        title="Python Developer",
        description="Backend services",
    )
    non_matching = make_job_result(
        provider="beta",
        provider_job_id="miss-1",
        title="Java Developer",
        description="Enterprise apps",
    )

    class MixedBatchProvider(FakeProvider):
        async def pages(self, filters):
            from jobs_back.providers.protocol import ProviderPageBatch

            del filters
            yield ProviderPageBatch(
                items=[matching, non_matching],
                page=1,
                total_pages=1,
            )

    manager = LiveSearchManager(
        provider=MixedBatchProvider(total_pages=1, items_per_page=0)
    )
    started = manager.start(uuid4(), SearchFilters(query="python"))
    for _ in range(40):
        await asyncio.sleep(0.01)
        snapshot = manager.page(started.state.id, 1, 25)
        assert snapshot is not None
        if snapshot.is_complete:
            break
    final = manager.page(started.state.id, 1, 25)
    assert final is not None
    assert final.total == 1
    assert final.items[0].provider_job_id == "match-1"
    await manager.close()


@pytest.mark.asyncio
async def test_query_membership_is_provider_independent() -> None:
    matching = make_job_result(
        provider="alpha",
        provider_job_id="match-1",
        title="Python Developer",
        description="Backend services",
    )
    non_matching = make_job_result(
        provider="beta",
        provider_job_id="miss-1",
        title="Java Developer",
        description="Enterprise apps",
    )

    class QueryIgnoringProvider(FakeProvider):
        async def pages(self, filters):
            from jobs_back.providers.protocol import ProviderPageBatch

            del filters
            yield ProviderPageBatch(
                items=[matching, non_matching],
                page=1,
                total_pages=1,
            )

    class QueryFilteringProvider(FakeProvider):
        def __init__(self) -> None:
            super().__init__(key="beta", total_pages=1, items_per_page=0)

        async def pages(self, filters):
            from jobs_back.providers.protocol import ProviderPageBatch

            if filters.query:
                yield ProviderPageBatch(items=[matching], page=1, total_pages=1)
            else:
                yield ProviderPageBatch(
                    items=[matching, non_matching],
                    page=1,
                    total_pages=1,
                )

    async def completed_ids(providers) -> list[str]:
        manager = LiveSearchManager(providers=providers)
        started = manager.start(uuid4(), SearchFilters(query="python"))
        for _ in range(40):
            await asyncio.sleep(0.01)
            snapshot = manager.page(started.state.id, 1, 25)
            assert snapshot is not None
            if snapshot.is_complete:
                break
        final = manager.page(started.state.id, 1, 25)
        assert final is not None
        ids = sorted(item.provider_job_id for item in final.items)
        await manager.close()
        return ids

    ignoring = [QueryIgnoringProvider(key="alpha", total_pages=1, items_per_page=0)]
    filtering = [
        QueryIgnoringProvider(key="alpha", total_pages=1, items_per_page=0),
        QueryFilteringProvider(),
    ]
    assert await completed_ids(ignoring) == ["match-1"]
    assert await completed_ids(filtering) == ["match-1"]


@pytest.mark.asyncio
async def test_location_filter_is_independent_from_country() -> None:
    provider = FakeProvider(
        total_pages=1,
        items_per_page=2,
        item_factory=lambda page, index: make_job_result(
            provider_job_id=f"job-{index}",
            title=f"Role {index}",
            location_text="Remote - US" if index == 0 else "Berlin, Germany",
            eligible_country_codes=["US"] if index == 0 else ["DE"],
        ),
    )
    manager = LiveSearchManager(provider=provider)
    started = manager.start(uuid4(), SearchFilters(location="berlin"))
    for _ in range(40):
        await asyncio.sleep(0.01)
        snapshot = manager.page(started.state.id, 1, 25)
        assert snapshot is not None
        if snapshot.is_complete:
            break
    final = manager.page(started.state.id, 1, 25)
    assert final is not None
    assert final.total == 1
    assert final.items[0].location_text == "Berlin, Germany"
    await manager.close()
