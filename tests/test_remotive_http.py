from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from jobs_back.providers.remotive import RESULT_CAP, RemotiveProvider
from jobs_back.schemas.discovery import SearchFilters

FIXTURES = Path(__file__).parent / "fixtures" / "remotive"


@pytest.mark.asyncio
async def test_filter_params_mapped() -> None:
    requests: list[str] = []
    payload = json.loads((FIXTURES / "sample.json").read_text())

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        return httpx.Response(200, json=payload)

    provider = RemotiveProvider()
    provider._client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://remotive.com/api",
    )
    filters = SearchFilters(query="python")
    pages = [batch async for batch in provider.pages(filters)]
    assert len(pages) == 1
    assert any("search=python" in url for url in requests)
    assert any(f"limit={RESULT_CAP}" in url for url in requests)
    await provider.close()


@pytest.mark.asyncio
async def test_cap_warning_on_broad_search() -> None:
    jobs = [
        {
            "id": i,
            "title": f"Role {i}",
            "company_name": "Co",
            "url": f"https://remotive.com/remote-jobs/{i}",
        }
        for i in range(RESULT_CAP)
    ]
    payload = {"jobs": jobs, "total-job-count": RESULT_CAP + 10}

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    provider = RemotiveProvider()
    provider._client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://remotive.com/api",
    )
    pages = [batch async for batch in provider.pages(SearchFilters())]
    assert any(f"truncated at {RESULT_CAP}" in w for w in pages[0].warnings)
    await provider.close()


@pytest.mark.asyncio
async def test_retry_after_on_429() -> None:
    attempts = 0
    payload = json.loads((FIXTURES / "sample.json").read_text())

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(200, json=payload)

    provider = RemotiveProvider()
    provider._client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://remotive.com/api",
    )
    pages = [batch async for batch in provider.pages(SearchFilters(query="react"))]
    assert attempts == 2
    assert len(pages[0].items) == 2
    await provider.close()


@pytest.mark.asyncio
async def test_timeout_surfaces_warning() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow")

    provider = RemotiveProvider(max_retries=1)
    provider._client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://remotive.com/api",
    )
    pages = [batch async for batch in provider.pages(SearchFilters())]
    assert pages[0].warnings
    await provider.close()
