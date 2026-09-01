from __future__ import annotations

import pytest

from jobs_back.providers.remotive import RemotiveProvider
from jobs_back.schemas.discovery import SearchFilters


@pytest.mark.live
@pytest.mark.asyncio
async def test_remotive_live_smoke() -> None:
    provider = RemotiveProvider()
    try:
        pages = [batch async for batch in provider.pages(SearchFilters(query="python"))]
        assert pages
        assert pages[0].items or pages[0].warnings
    finally:
        await provider.close()
