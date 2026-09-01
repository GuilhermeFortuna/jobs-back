from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from jobs_back.providers.weworkremotely import FEED_ITEM_CAP, WeWorkRemotelyProvider
from jobs_back.schemas.discovery import SearchFilters

FIXTURES = Path(__file__).parent / "fixtures" / "weworkremotely"


@pytest.mark.asyncio
async def test_bulk_response_yields_batches() -> None:
    feed = (FIXTURES / "sample.rss").read_text()

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=feed)

    provider = WeWorkRemotelyProvider(batch_size=2)
    provider._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    pages = [batch async for batch in provider.pages(SearchFilters())]
    assert len(pages) == 2
    assert pages[0].total_pages == 2
    assert len(pages[0].items) == 2
    assert len(pages[1].items) == 1
    await provider.close()


@pytest.mark.asyncio
async def test_feed_limit_warning() -> None:
    items = "\n".join(
        f"""    <item>
      <title>Co {i}: Role {i}</title>
      <description>&lt;p&gt;Desc&lt;/p&gt;</description>
      <pubDate>Tue, 01 Sep 2026 12:00:00 +0000</pubDate>
      <guid>https://weworkremotely.com/remote-jobs/role-{i}</guid>
      <link>https://weworkremotely.com/remote-jobs/role-{i}</link>
    </item>"""
        for i in range(FEED_ITEM_CAP)
    )
    feed = (
        f'<?xml version="1.0"?><rss><channel><title>WWR</title>{items}</channel></rss>'
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=feed)

    provider = WeWorkRemotelyProvider()
    provider._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    pages = [batch async for batch in provider.pages(SearchFilters())]
    assert any(f"truncated at {FEED_ITEM_CAP}" in w for w in pages[0].warnings)
    await provider.close()


@pytest.mark.asyncio
async def test_retry_after_on_429() -> None:
    attempts = 0
    feed = (FIXTURES / "sample.rss").read_text()

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(200, text=feed)

    provider = WeWorkRemotelyProvider()
    provider._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    pages = [batch async for batch in provider.pages(SearchFilters())]
    assert attempts == 2
    assert len(pages[0].items) == 3
    await provider.close()


@pytest.mark.asyncio
async def test_timeout_surfaces_warning() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow")

    provider = WeWorkRemotelyProvider(max_retries=1)
    provider._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    pages = [batch async for batch in provider.pages(SearchFilters())]
    assert pages[0].warnings
    await provider.close()
