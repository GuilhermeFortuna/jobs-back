from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from jobs_back.db import get_db
from jobs_back.models.profile import Profile
from jobs_back.schemas.discovery import (
    SearchCreate,
    SearchFilters,
    SearchPage,
    SearchRefreshPage,
)
from jobs_back.search.live import LiveSearchManager, SearchStartResult
from jobs_back.services.exceptions import SearchExpiredError

router = APIRouter(tags=["search"])


def get_manager(request: Request) -> LiveSearchManager:
    return request.app.state.search_manager


def _search_page_or_error(
    manager: LiveSearchManager,
    search_id: UUID,
    page: int,
    page_size: int,
) -> SearchPage:
    try:
        result = manager.page(search_id, page, page_size)
    except SearchExpiredError as exc:
        raise HTTPException(status.HTTP_410_GONE, str(exc)) from exc
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Search not found")
    return result


def _refresh_page(
    manager: LiveSearchManager,
    result: SearchStartResult,
    page: int,
    page_size: int,
) -> SearchRefreshPage:
    snapshot = _search_page_or_error(manager, result.state.id, page, page_size)
    return SearchRefreshPage(
        **snapshot.model_dump(),
        previous_search_id=result.previous_search_id,
        serving_search_id=result.serving_search_id or result.state.id,
    )


@router.post(
    "/searches",
    response_model=SearchPage,
    status_code=status.HTTP_202_ACCEPTED,
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
    started = manager.start(profile.id, filters)
    return _search_page_or_error(manager, started.state.id, 1, 25)


@router.get(
    "/searches/{search_id}",
    response_model=SearchPage,
    responses={
        404: {"description": "Search not found"},
        410: {"description": "Search expired or evicted"},
    },
)
def get_search(
    search_id: UUID,
    manager: Annotated[LiveSearchManager, Depends(get_manager)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> SearchPage:
    return _search_page_or_error(manager, search_id, page, page_size)


@router.post(
    "/profiles/{profile_id}/default-search/refresh",
    response_model=SearchRefreshPage,
    status_code=202,
    responses={
        404: {"description": "Profile not found"},
        410: {"description": "Search expired or evicted"},
    },
)
async def refresh_default_search(
    profile_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    manager: Annotated[LiveSearchManager, Depends(get_manager)],
) -> SearchRefreshPage:
    profile = db.get(Profile, profile_id)
    if profile is None:
        raise HTTPException(404, "Profile not found")
    started = manager.start(
        profile.id, SearchFilters.model_validate(profile.preferences), force=True
    )
    return _refresh_page(manager, started, 1, 25)
