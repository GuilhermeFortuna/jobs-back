from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from jobs_back.schemas.discovery import SearchFilters
from tests.helpers.discovery import make_job_result
from tests.helpers.fake_provider import FakeProvider, multi_provider_manager


def _item(provider: str, job_id: str, posted: datetime) -> object:
    return make_job_result(
        provider=provider,
        provider_job_id=job_id,
        title=f"{provider}-{job_id}",
        posted_at=posted,
    )


@pytest.mark.asyncio
async def test_identical_completed_pages_regardless_of_arrival_order() -> None:
    posted = datetime(2026, 1, 15, tzinfo=UTC)
    factory_a = lambda _p, _i: _item("alpha", "a1", posted)  # noqa: E731
    factory_b = lambda _p, _i: _item("beta", "b1", posted)  # noqa: E731
    orderings = [
        [
            FakeProvider(
                key="alpha",
                total_pages=1,
                items_per_page=1,
                item_factory=factory_a,
                delay=0.05,
            ),
            FakeProvider(
                key="beta",
                total_pages=1,
                items_per_page=1,
                item_factory=factory_b,
            ),
        ],
        [
            FakeProvider(
                key="beta",
                total_pages=1,
                items_per_page=1,
                item_factory=factory_b,
                delay=0.05,
            ),
            FakeProvider(
                key="alpha",
                total_pages=1,
                items_per_page=1,
                item_factory=factory_a,
            ),
        ],
    ]
    pages: list[list[tuple[str, str]]] = []
    for providers in orderings:
        manager = multi_provider_manager(providers)
        started = manager.start(uuid4(), SearchFilters(sort="newest"))
        for _ in range(60):
            await asyncio.sleep(0.01)
            snapshot = manager.page(started.state.id, 1, 25)
            assert snapshot is not None
            if snapshot.is_complete:
                break
        final = manager.page(started.state.id, 1, 25)
        assert final is not None
        pages.append([(item.provider, item.provider_job_id) for item in final.items])
        await manager.close()
    assert pages[0] == pages[1]
