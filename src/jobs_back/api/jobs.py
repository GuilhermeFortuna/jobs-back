"""Job search and detail endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from jobs_back.db import get_db
from jobs_back.schemas.job import JobDetail
from jobs_back.schemas.job_search import JobPage, JobSearchParams, job_search_params
from jobs_back.services.job_search import get_job_by_id, search_jobs

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=JobPage)
def list_jobs(
    params: Annotated[JobSearchParams, Depends(job_search_params)],
    db: Annotated[Session, Depends(get_db)],
) -> JobPage:
    """Return a filtered, paginated page of active jobs."""
    return search_jobs(db, params)


@router.get("/{job_id}", response_model=JobDetail)
def get_job(
    job_id: UUID,
    db: Annotated[Session, Depends(get_db)],
) -> JobDetail:
    """Return one job by UUID (active or inactive)."""
    job = get_job_by_id(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
