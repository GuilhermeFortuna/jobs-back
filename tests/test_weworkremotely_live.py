from __future__ import annotations

import pytest

from jobs_back.providers.weworkremotely import WeWorkRemotelyProvider
from jobs_back.schemas.discovery import SearchFilters


@pytest.mark.live
@pytest.mark.asyncio
async def test_weworkremotely_live_smoke() -> None:
    provider = WeWorkRemotelyProvider()
    try:
        pages = [batch async for batch in provider.pages(SearchFilters())]
        assert pages
        assert pages[0].items or pages[0].warnings
    finally:
        await provider.close()
