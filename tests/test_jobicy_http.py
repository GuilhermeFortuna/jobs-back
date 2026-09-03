from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from jobs_back.providers.jobicy import RESULT_CAP, JobicyProvider
from jobs_back.schemas.discovery import SearchFilters

FIXTURES = Path(__file__).parent / "fixtures" / "jobicy"


@pytest.mark.asyncio
async def test_filter_params_mapped() -> None:
    requests: list[str] = []
    payload = json.loads((FIXTURES / "sample.json").read_text())

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        return httpx.Response(200, json=payload)

    provider = JobicyProvider()
    provider._client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://jobicy.com/api/v2",
    )
    filters = SearchFilters(query="python", country="USA")
    pages = [batch async for batch in provider.pages(filters)]
    assert len(pages) == 1
    assert any("tag=python" in url for url in requests)
    assert any("geo=USA" in url for url in requests)
    await provider.close()


@pytest.mark.asyncio
async def test_cap_warning_on_broad_search() -> None:
    jobs = [
        {
            "id": i,
            "jobTitle": f"Role {i}",
            "companyName": "Co",
            "url": f"https://j/{i}",
        }
        for i in range(RESULT_CAP)
    ]
    payload = {"jobs": jobs}

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    provider = JobicyProvider()
    provider._client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://jobicy.com/api/v2",
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

    provider = JobicyProvider()
    provider._client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://jobicy.com/api/v2",
    )
    pages = [batch async for batch in provider.pages(SearchFilters(country="USA"))]
    assert attempts == 2
    assert len(pages[0].items) == 1
    await provider.close()
