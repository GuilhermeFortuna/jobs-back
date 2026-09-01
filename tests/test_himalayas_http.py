from __future__ import annotations

import httpx
import pytest

from jobs_back.providers.himalayas import HimalayasProvider
from jobs_back.schemas.discovery import SearchFilters


def _payload(page: int, *, total: int = 40, page_size: int = 20) -> dict:
    jobs = [
        {"guid": f"job-{page}-{index}", "title": f"Role {index}"}
        for index in range(page_size)
    ]
    return {"jobs": jobs, "totalCount": total, "limit": page_size, "page": page}


@pytest.mark.asyncio
async def test_upstream_params_include_filters() -> None:
    requests: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        page = int(request.url.params.get("page", "1"))
        return httpx.Response(200, json=_payload(page))

    provider = HimalayasProvider(concurrency=2)
    provider._client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://himalayas.app"
    )
    filters = SearchFilters(
        query="python",
        country="United States",
        worldwide=True,
        seniority=["senior"],
        employment_types=["full_time"],
        sort="salary",
    )
    pages = [batch async for batch in provider.pages(filters)]
    assert len(pages) == 2
    assert any("q=python" in url for url in requests)
    assert any("country=United+States" in url for url in requests)
    assert any("worldwide=true" in url for url in requests)
    assert any("employment_type=Full+Time" in url for url in requests)
    assert any("sort=salaryDesc" in url for url in requests)
    await provider.close()


@pytest.mark.asyncio
async def test_retry_after_on_429() -> None:
    attempts = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        page = int(request.url.params.get("page", "1"))
        return httpx.Response(200, json=_payload(page, total=20, page_size=20))

    provider = HimalayasProvider(concurrency=1, max_retries=3)
    provider._client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://himalayas.app"
    )
    batches = [batch async for batch in provider.pages(SearchFilters())]
    assert batches
    assert attempts >= 2
    await provider.close()


@pytest.mark.asyncio
async def test_partial_page_failure_yields_warning() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params.get("page", "1"))
        if page == 2:
            return httpx.Response(500, json={"error": "boom"})
        return httpx.Response(200, json=_payload(page))

    provider = HimalayasProvider(concurrency=2, max_retries=1)
    provider._client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://himalayas.app"
    )
    batches = [batch async for batch in provider.pages(SearchFilters())]
    assert len(batches) == 2
    assert batches[0].items
    assert batches[1].warnings
    await provider.close()
