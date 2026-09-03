from __future__ import annotations

import pytest

from jobs_back.providers.remoteok import RemoteOKProvider
from jobs_back.schemas.discovery import SearchFilters


@pytest.mark.live
@pytest.mark.asyncio
async def test_remoteok_live_smoke() -> None:
    provider = RemoteOKProvider()
    try:
        pages = [batch async for batch in provider.pages(SearchFilters())]
        assert pages
        assert pages[0].items or pages[0].warnings
    finally:
        await provider.close()
