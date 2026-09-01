from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from jobs_back.api.searches import get_manager
from jobs_back.providers.registry import provider_display_name
from jobs_back.schemas.discovery import ProviderDescriptor
from jobs_back.search.live import LiveSearchManager

router = APIRouter(tags=["providers"])


@router.get("/providers", response_model=list[ProviderDescriptor])
def list_providers(
    manager: Annotated[LiveSearchManager, Depends(get_manager)],
) -> list[ProviderDescriptor]:
    """Providers a search will actually fan into.

    Sourced from the live adapters rather than from configuration, so a client
    can never offer a filter for a provider the manager will not query.
    """
    return [
        ProviderDescriptor(
            key=provider.key,
            display_name=provider_display_name(provider.key),
        )
        for provider in manager.providers
    ]
