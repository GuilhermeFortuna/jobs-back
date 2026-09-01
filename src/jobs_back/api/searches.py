from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from jobs_back.db import get_db
from jobs_back.models.profile import Profile
from jobs_back.schemas.discovery import SearchCreate, SearchFilters, SearchPage
from jobs_back.search.live import LiveSearchManager

router = APIRouter(tags=["search"])


def get_manager(request: Request) -> LiveSearchManager:
    return request.app.state.search_manager


@router.post(
    "/searches", response_model=SearchPage, status_code=status.HTTP_202_ACCEPTED
)
async def create_search(
    body: SearchCreate,
    db: Annotated[Session, Depends(get_db)],
    manager: Annotated[LiveSearchManager, Depends(get_manager)],
) -> SearchPage:
    profile = db.get(Profile, body.profile_id)
    if profile is None:
        raise HTTPException(404, "Profile not found")
    filters = body.filters or SearchFilters.model_validate(profile.preferences)
    state = manager.start(profile.id, filters)
    return manager.page(state.id, 1, 25)  # type: ignore[return-value]


@router.get("/searches/{search_id}", response_model=SearchPage)
def get_search(
    search_id: UUID,
    manager: Annotated[LiveSearchManager, Depends(get_manager)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> SearchPage:
    result = manager.page(search_id, page, page_size)
    if result is None:
        raise HTTPException(404, "Search not found or expired")
    return result


@router.post(
    "/profiles/{profile_id}/default-search/refresh",
    response_model=SearchPage,
    status_code=202,
)
async def refresh_default_search(
    profile_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    manager: Annotated[LiveSearchManager, Depends(get_manager)],
) -> SearchPage:
    profile = db.get(Profile, profile_id)
    if profile is None:
        raise HTTPException(404, "Profile not found")
    state = manager.start(
        profile.id, SearchFilters.model_validate(profile.preferences), force=True
    )
    return manager.page(state.id, 1, 25)  # type: ignore[return-value]
