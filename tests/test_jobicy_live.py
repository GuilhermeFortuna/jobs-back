from __future__ import annotations

import pytest

from jobs_back.providers.jobicy import JobicyProvider
from jobs_back.schemas.discovery import SearchFilters


@pytest.mark.live
@pytest.mark.asyncio
async def test_jobicy_live_smoke() -> None:
    provider = JobicyProvider()
    try:
        pages = [batch async for batch in provider.pages(SearchFilters(country="USA"))]
        assert pages
        assert pages[0].items or pages[0].warnings
    finally:
        await provider.close()
