from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from jobs_back.config import Settings, get_settings
from jobs_back.providers.registry import (
    KNOWN_KEYS,
    provider_display_name,
    resolve_all_provider_states,
)
from jobs_back.schemas.discovery import ProviderDescriptor

router = APIRouter(tags=["providers"])


@router.get("/providers", response_model=list[ProviderDescriptor])
def list_providers(
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[ProviderDescriptor]:
    """Every known provider and whether it will participate in search.

    Enabled providers match the live adapters the manager holds. Unconfigured
    and disabled providers are reported from the resolved registry view with no
    credential detail.
    """
    states = resolve_all_provider_states(settings)
    return [
        ProviderDescriptor(
            key=key,
            display_name=provider_display_name(key),
            state=states[key],
        )
        for key in KNOWN_KEYS
    ]
