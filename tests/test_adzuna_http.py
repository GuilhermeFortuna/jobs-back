from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from jobs_back.providers.adzuna import AdzunaProvider
from jobs_back.schemas.discovery import SearchFilters

FIXTURES = Path(__file__).parent / "fixtures" / "adzuna"


def _sample_page(*, page: int, total: int = 40, page_size: int = 20) -> dict:
    payload = json.loads((FIXTURES / "sample.json").read_text())
    payload["count"] = total
    payload["results"] = [
        {
            "id": f"{page}-{index}",
            "title": f"Role {index}",
            "redirect_url": f"https://www.adzuna.co.uk/jobs/{page}-{index}",
            "company": {"display_name": "Co"},
            "location": {"display_name": "London"},
            "created": "2024-01-01T00:00:00Z",
        }
        for index in range(page_size)
    ]
    return payload


@pytest.mark.asyncio
async def test_upstream_params_include_filters_and_country() -> None:
    requests: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        page = int(request.url.path.rsplit("/", 1)[-1])
        return httpx.Response(200, json=_sample_page(page=page))

    provider = AdzunaProvider(
        app_id="test-id",
        app_key="test-key",
        default_country="gb",
        concurrency=2,
    )
    provider._client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://api.adzuna.com/v1/api/jobs",
    )
    filters = SearchFilters(
        query="python",
        location="London",
        country="us",
        minimum_salary=50000,
        employment_types=["full_time", "part_time"],
        posted_within_days=7,
    )
    pages = [batch async for batch in provider.pages(filters)]
    assert len(pages) == 2
    assert any("/us/search/" in url for url in requests)
    assert any("what=python" in url for url in requests)
    assert any("where=London" in url for url in requests)
    assert any("salary_min=50000" in url for url in requests)
    assert any("max_days_old=7" in url for url in requests)
    assert any("full_time=1" in url for url in requests)
    assert any("part_time=1" in url for url in requests)
    await provider.close()


@pytest.mark.asyncio
async def test_empty_country_uses_default() -> None:
    requests: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.path)
        return httpx.Response(200, json=_sample_page(page=1, total=5, page_size=5))

    provider = AdzunaProvider(
        app_id="test-id",
        app_key="test-key",
        default_country="gb",
        concurrency=1,
    )
    provider._client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://api.adzuna.com/v1/api/jobs",
    )
    batches = [batch async for batch in provider.pages(SearchFilters())]
    assert batches
    assert batches[0].items[0].provider_payload["queried_country"] == "gb"
    assert any("gb/search/" in path for path in requests)
    await provider.close()


@pytest.mark.asyncio
async def test_retry_after_on_transient_429() -> None:
    attempts = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        page = int(request.url.path.rsplit("/", 1)[-1])
        return httpx.Response(200, json=_sample_page(page=page, total=5, page_size=5))

    provider = AdzunaProvider(
        app_id="test-id",
        app_key="test-key",
        max_retries=3,
        concurrency=1,
    )
    provider._client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://api.adzuna.com/v1/api/jobs",
    )
    batches = [batch async for batch in provider.pages(SearchFilters())]
    assert batches
    assert attempts >= 2
    await provider.close()


@pytest.mark.asyncio
async def test_quota_rejection_is_not_retried() -> None:
    attempts = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(
            429,
            json={"exception": "Daily quota exceeded"},
        )

    provider = AdzunaProvider(
        app_id="test-id",
        app_key="test-key",
        max_retries=3,
        concurrency=1,
    )
    provider._client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://api.adzuna.com/v1/api/jobs",
    )
    batches = [batch async for batch in provider.pages(SearchFilters())]
    assert batches
    assert batches[0].warnings
    assert any("quota" in warning.lower() for warning in batches[0].warnings)
    assert attempts == 1
    await provider.close()


@pytest.mark.asyncio
async def test_request_budget_stops_paging() -> None:
    requests = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        page = int(request.url.path.rsplit("/", 1)[-1])
        return httpx.Response(200, json=_sample_page(page=page))

    provider = AdzunaProvider(
        app_id="test-id",
        app_key="test-key",
        request_budget=1,
        concurrency=2,
    )
    provider._client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://api.adzuna.com/v1/api/jobs",
    )
    batches = [batch async for batch in provider.pages(SearchFilters())]
    assert requests == 1
    assert any(
        any("budget" in warning.lower() for warning in batch.warnings)
        for batch in batches
    )
    await provider.close()


@pytest.mark.asyncio
async def test_request_budget_resets_for_each_search() -> None:
    requests = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(200, json=_sample_page(page=1, total=5, page_size=5))

    provider = AdzunaProvider(
        app_id="test-id",
        app_key="test-key",
        request_budget=1,
        concurrency=1,
    )
    provider._client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://api.adzuna.com/v1/api/jobs",
    )
    first = [batch async for batch in provider.pages(SearchFilters())]
    second = [batch async for batch in provider.pages(SearchFilters())]
    assert requests == 2
    assert first and second
    await provider.close()


@pytest.mark.asyncio
async def test_honest_total_pages() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.path.rsplit("/", 1)[-1])
        return httpx.Response(200, json=_sample_page(page=page, total=40, page_size=20))

    provider = AdzunaProvider(
        app_id="test-id",
        app_key="test-key",
        concurrency=2,
        request_budget=10,
    )
    provider._client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://api.adzuna.com/v1/api/jobs",
    )
    batches = [batch async for batch in provider.pages(SearchFilters())]
    assert batches[0].total_pages == 2
    await provider.close()
