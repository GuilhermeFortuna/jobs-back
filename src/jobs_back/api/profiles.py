from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from jobs_back.api.searches import get_manager
from jobs_back.db import get_db
from jobs_back.models.profile import Profile
from jobs_back.models.saved_job import SavedJob
from jobs_back.schemas.discovery import (
    ProfileCreate,
    ProfilePatch,
    ProfileRead,
    SavedJobCreate,
    SavedJobPatch,
    SavedJobRead,
)
from jobs_back.search.live import LiveSearchManager
from jobs_back.services import profile_library as library
from jobs_back.services.exceptions import (
    DuplicateProfileNameError,
    NotFoundError,
    SearchExpiredError,
    SearchJobNotFoundError,
)

router = APIRouter(prefix="/profiles", tags=["profiles"])


def _not_found(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, detail)


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, detail)


def _gone(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_410_GONE, detail)


@router.get("", response_model=list[ProfileRead])
def list_profiles(db: Annotated[Session, Depends(get_db)]) -> list[Profile]:
    return library.list_profiles(db)


@router.post(
    "",
    response_model=ProfileRead,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"description": "Duplicate profile name"}},
)
def create_profile(
    body: ProfileCreate, db: Annotated[Session, Depends(get_db)]
) -> Profile:
    try:
        return library.create_profile(db, body)
    except DuplicateProfileNameError as exc:
        raise _conflict(str(exc)) from exc


@router.get(
    "/{profile_id}",
    response_model=ProfileRead,
    responses={404: {"description": "Profile not found"}},
)
def get_profile(profile_id: UUID, db: Annotated[Session, Depends(get_db)]) -> Profile:
    try:
        return library.get_profile(db, profile_id)
    except NotFoundError as exc:
        raise _not_found(str(exc)) from exc


@router.patch(
    "/{profile_id}",
    response_model=ProfileRead,
    responses={
        404: {"description": "Profile not found"},
        409: {"description": "Duplicate profile name"},
    },
)
def patch_profile(
    body: ProfilePatch, profile_id: UUID, db: Annotated[Session, Depends(get_db)]
) -> Profile:
    try:
        return library.update_profile(db, profile_id, body)
    except NotFoundError as exc:
        raise _not_found(str(exc)) from exc
    except DuplicateProfileNameError as exc:
        raise _conflict(str(exc)) from exc


@router.get(
    "/{profile_id}/jobs",
    response_model=list[SavedJobRead],
    responses={404: {"description": "Profile not found"}},
)
def list_saved_jobs(
    profile_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    state_filter: Annotated[
        Literal["saved", "applied"] | None, Query(alias="state")
    ] = None,
) -> list[SavedJob]:
    try:
        return library.list_library_jobs(db, profile_id, state=state_filter)
    except NotFoundError as exc:
        raise _not_found(str(exc)) from exc


@router.post(
    "/{profile_id}/jobs",
    response_model=SavedJobRead,
    responses={
        201: {"description": "Job saved to library"},
        200: {"description": "Existing library row updated"},
        404: {"description": "Profile or search job not found"},
        410: {"description": "Search expired or evicted"},
    },
)
def save_job(
    body: SavedJobCreate,
    profile_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    manager: Annotated[LiveSearchManager, Depends(get_manager)],
    response: Response,
) -> SavedJob:
    try:
        job, created = library.save_library_job(db, profile_id, body, manager)
    except NotFoundError as exc:
        raise _not_found(str(exc)) from exc
    except SearchExpiredError as exc:
        raise _gone(str(exc)) from exc
    except SearchJobNotFoundError as exc:
        raise _not_found(str(exc)) from exc
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return job


@router.get(
    "/{profile_id}/jobs/{job_id}",
    response_model=SavedJobRead,
    responses={404: {"description": "Saved job not found"}},
)
def get_saved_job(
    profile_id: UUID, job_id: UUID, db: Annotated[Session, Depends(get_db)]
) -> SavedJob:
    try:
        return library.get_library_job(db, profile_id, job_id)
    except NotFoundError as exc:
        raise _not_found(str(exc)) from exc


@router.patch(
    "/{profile_id}/jobs/{job_id}",
    response_model=SavedJobRead,
    responses={404: {"description": "Saved job not found"}},
)
def patch_job(
    body: SavedJobPatch,
    profile_id: UUID,
    job_id: UUID,
    db: Annotated[Session, Depends(get_db)],
) -> SavedJob:
    try:
        return library.update_library_job_state(db, profile_id, job_id, body.state)
    except NotFoundError as exc:
        raise _not_found(str(exc)) from exc


@router.delete(
    "/{profile_id}/jobs/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"description": "Saved job not found"}},
)
def delete_job(
    profile_id: UUID, job_id: UUID, db: Annotated[Session, Depends(get_db)]
) -> Response:
    try:
        library.delete_library_job(db, profile_id, job_id)
    except NotFoundError as exc:
        raise _not_found(str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
