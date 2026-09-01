from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from jobs_back.providers.remoteok import RemoteOKProvider
from jobs_back.schemas.discovery import SearchFilters

FIXTURES = Path(__file__).parent / "fixtures" / "remoteok"


@pytest.mark.asyncio
async def test_bulk_response_yields_batches() -> None:
    payload = json.loads((FIXTURES / "sample.json").read_text())

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    provider = RemoteOKProvider(batch_size=1)
    provider._client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://remoteok.com"
    )
    pages = [batch async for batch in provider.pages(SearchFilters())]
    assert len(pages) == 1
    assert len(pages[0].items) == 1
    assert pages[0].total_pages == 1
    await provider.close()


@pytest.mark.asyncio
async def test_retry_after_on_429() -> None:
    attempts = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(
            200,
            json=[
                {"legal": "ok"},
                {
                    "id": "1",
                    "position": "Dev",
                    "company": "Co",
                    "url": "https://x",
                },
            ],
        )

    provider = RemoteOKProvider()
    provider._client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://remoteok.com"
    )
    pages = [batch async for batch in provider.pages(SearchFilters())]
    assert attempts == 2
    assert len(pages[0].items) == 1
    await provider.close()


@pytest.mark.asyncio
async def test_timeout_surfaces_warning() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow")

    provider = RemoteOKProvider(max_retries=1)
    provider._client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://remoteok.com"
    )
    pages = [batch async for batch in provider.pages(SearchFilters())]
    assert pages[0].warnings
    await provider.close()
