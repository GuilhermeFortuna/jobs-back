"""Trusted profiles and personal job library operations."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from jobs_back.models.profile import Profile
from jobs_back.models.saved_job import SavedJob
from jobs_back.normalization.dedup import derive_dedup_key
from jobs_back.schemas.discovery import (
    JobResult,
    ProfileCreate,
    ProfilePatch,
    SavedJobCreate,
    SearchFilters,
)
from jobs_back.search.live import LiveSearchManager
from jobs_back.services.exceptions import (
    DuplicateProfileNameError,
    NotFoundError,
)
from jobs_back.services.library_dedup import alternate_sources_payload

_DUPLICATE_PROFILE_NAME = "A profile with that name already exists"

LibraryState = Literal["saved", "applied"]


def _now() -> datetime:
    return datetime.now(UTC)


def _relevant_timestamp_order():
    return (
        case(
            (SavedJob.state == "applied", SavedJob.applied_at),
            else_=SavedJob.saved_at,
        ).desc(),
        SavedJob.id.desc(),
    )


def _apply_state(job: SavedJob, state: LibraryState, *, now: datetime) -> None:
    if job.state == state:
        return
    job.state = state
    if state == "applied":
        if job.applied_at is None:
            job.applied_at = now
    else:
        job.applied_at = None
    job.updated_at = now


def _snapshot_values(result: JobResult, state: LibraryState, *, now: datetime) -> dict:
    applied_at = now if state == "applied" else None
    return {
        "provider": result.provider,
        "provider_job_id": result.provider_job_id,
        "state": state,
        "title": result.title,
        "company": result.company,
        "description": result.description,
        "location_text": result.location_text,
        "eligible_country_codes": result.eligible_country_codes,
        "employment_type": result.employment_type,
        "remote_type": result.remote_type,
        "seniority": result.seniority,
        "salary_min_annual": result.salary_min_annual,
        "salary_max_annual": result.salary_max_annual,
        "salary_currency": result.salary_currency,
        "job_url": str(result.job_url),
        "apply_url": str(result.apply_url) if result.apply_url else None,
        "company_logo_url": (
            str(result.company_logo_url) if result.company_logo_url else None
        ),
        "posted_at": result.posted_at,
        "provider_payload": result.provider_payload,
        "dedup_key": derive_dedup_key(result),
        "alternate_sources": alternate_sources_payload(result),
        "saved_at": now,
        "applied_at": applied_at,
        "updated_at": now,
    }


def _refresh_snapshot_fields(
    job: SavedJob,
    result: JobResult,
    *,
    now: datetime,
) -> None:
    job.provider = result.provider
    job.provider_job_id = result.provider_job_id
    job.title = result.title
    job.company = result.company
    job.description = result.description
    job.location_text = result.location_text
    job.eligible_country_codes = result.eligible_country_codes
    job.employment_type = result.employment_type
    job.remote_type = result.remote_type
    job.seniority = result.seniority
    job.salary_min_annual = result.salary_min_annual
    job.salary_max_annual = result.salary_max_annual
    job.salary_currency = result.salary_currency
    job.job_url = str(result.job_url)
    job.apply_url = str(result.apply_url) if result.apply_url else None
    job.company_logo_url = (
        str(result.company_logo_url) if result.company_logo_url else None
    )
    job.posted_at = result.posted_at
    job.provider_payload = result.provider_payload
    job.dedup_key = derive_dedup_key(result)
    job.updated_at = now


def list_profiles(session: Session) -> list[Profile]:
    return list(session.scalars(select(Profile).order_by(Profile.display_name)))


def create_profile(session: Session, body: ProfileCreate) -> Profile:
    profile = Profile(
        display_name=body.display_name.strip(),
        preferences=body.preferences.model_dump(mode="json"),
    )
    session.add(profile)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise DuplicateProfileNameError(_DUPLICATE_PROFILE_NAME) from exc
    session.refresh(profile)
    return profile


def get_profile(session: Session, profile_id: UUID) -> Profile:
    profile = session.get(Profile, profile_id)
    if profile is None:
        raise NotFoundError("Profile not found")
    return profile


def update_profile(session: Session, profile_id: UUID, body: ProfilePatch) -> Profile:
    profile = get_profile(session, profile_id)
    if body.display_name is not None:
        profile.display_name = body.display_name.strip()
    if body.preferences is not None:
        profile.preferences = body.preferences.model_dump(mode="json")
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise DuplicateProfileNameError(_DUPLICATE_PROFILE_NAME) from exc
    session.refresh(profile)
    return profile


def list_library_jobs(
    session: Session,
    profile_id: UUID,
    *,
    state: LibraryState | None = None,
) -> list[SavedJob]:
    get_profile(session, profile_id)
    statement = select(SavedJob).where(SavedJob.profile_id == profile_id)
    if state is not None:
        statement = statement.where(SavedJob.state == state)
    return list(session.scalars(statement.order_by(*_relevant_timestamp_order())))


def get_library_job(session: Session, profile_id: UUID, job_id: UUID) -> SavedJob:
    job = session.scalar(
        select(SavedJob).where(
            SavedJob.id == job_id,
            SavedJob.profile_id == profile_id,
        )
    )
    if job is None:
        raise NotFoundError("Saved job not found")
    return job


def _merge_into_existing_by_dedup(
    session: Session,
    existing: SavedJob,
    result: JobResult,
    *,
    now: datetime,
) -> SavedJob:
    _refresh_snapshot_fields(existing, result, now=now)
    existing.alternate_sources = alternate_sources_payload(result)
    session.commit()
    session.refresh(existing)
    return existing


def save_library_job(
    session: Session,
    profile_id: UUID,
    body: SavedJobCreate,
    manager: LiveSearchManager,
) -> tuple[SavedJob, bool]:
    """Return the saved job and whether it was newly inserted."""
    get_profile(session, profile_id)
    result = manager.resolve_job(
        body.search_id,
        profile_id,
        body.provider,
        body.provider_job_id,
    )
    dedup_key = derive_dedup_key(result)
    now = _now()
    existing_id = session.scalar(
        select(SavedJob.id).where(
            SavedJob.profile_id == profile_id,
            SavedJob.provider == body.provider,
            SavedJob.provider_job_id == body.provider_job_id,
        )
    )
    created = existing_id is None

    if created:
        existing_by_dedup = session.scalar(
            select(SavedJob).where(
                SavedJob.profile_id == profile_id,
                SavedJob.dedup_key == dedup_key,
            )
        )
        if existing_by_dedup is not None:
            job = _merge_into_existing_by_dedup(
                session,
                existing_by_dedup,
                result,
                now=now,
            )
            return job, False

    snapshot = _snapshot_values(result, body.state, now=now)
    insert_stmt = insert(SavedJob).values(profile_id=profile_id, **snapshot)
    excluded = insert_stmt.excluded
    upsert = insert_stmt.on_conflict_do_update(
        constraint="uq_saved_jobs_profile_provider",
        set_={
            "title": excluded.title,
            "company": excluded.company,
            "description": excluded.description,
            "location_text": excluded.location_text,
            "eligible_country_codes": excluded.eligible_country_codes,
            "employment_type": excluded.employment_type,
            "remote_type": excluded.remote_type,
            "seniority": excluded.seniority,
            "salary_min_annual": excluded.salary_min_annual,
            "salary_max_annual": excluded.salary_max_annual,
            "salary_currency": excluded.salary_currency,
            "job_url": excluded.job_url,
            "apply_url": excluded.apply_url,
            "company_logo_url": excluded.company_logo_url,
            "posted_at": excluded.posted_at,
            "provider_payload": excluded.provider_payload,
            "dedup_key": excluded.dedup_key,
            "alternate_sources": excluded.alternate_sources,
            "updated_at": excluded.updated_at,
            "state": excluded.state,
            "applied_at": case(
                (excluded.state == "saved", None),
                else_=func.coalesce(SavedJob.applied_at, excluded.applied_at),
            ),
        },
    ).returning(SavedJob.id)

    job_id = session.scalar(upsert)
    session.commit()
    job = session.get(SavedJob, job_id)
    if job is None:
        raise NotFoundError("Saved job not found")
    return job, created


def update_library_job_state(
    session: Session,
    profile_id: UUID,
    job_id: UUID,
    state: LibraryState,
) -> SavedJob:
    job = get_library_job(session, profile_id, job_id)
    now = _now()
    previous_state = job.state
    _apply_state(job, state, now=now)
    if previous_state != state:
        session.commit()
        session.refresh(job)
    return job


def delete_library_job(session: Session, profile_id: UUID, job_id: UUID) -> None:
    job = get_library_job(session, profile_id, job_id)
    session.delete(job)
    session.commit()


def validate_profile_preferences(preferences: dict) -> SearchFilters:
    return SearchFilters.model_validate(preferences)
