"""Upsert and lifecycle logic for provider job ingestion."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from jobs_back.ingestion.exceptions import AdapterRecordValidationError
from jobs_back.models.enums import JobStatus, SyncMode
from jobs_back.models.job import Job
from jobs_back.schemas.job import NormalizedJobInput


@dataclass(frozen=True)
class UpsertCounts:
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    reactivated: int = 0
    deactivated: int = 0


def apply_jobs(
    session: Session,
    *,
    provider: str,
    jobs: list[NormalizedJobInput],
    run_at: datetime,
    sync_mode: SyncMode,
) -> UpsertCounts:
    """Upsert jobs and apply full-snapshot deactivation in one transaction."""
    seen_ids: list[str] = []
    created = updated = unchanged = reactivated = 0

    for job_input in jobs:
        if job_input.provider != provider:
            raise AdapterRecordValidationError(
                "Adapter job provider does not match the selected provider",
            )
        seen_ids.append(job_input.provider_job_id)
        existing = session.execute(
            select(Job).where(
                Job.provider == provider,
                Job.provider_job_id == job_input.provider_job_id,
            )
        ).scalar_one_or_none()

        if existing is None:
            session.add(_job_from_input(job_input, run_at))
            created += 1
            continue

        was_inactive = existing.status == JobStatus.INACTIVE.value
        existing.last_seen_at = run_at

        if was_inactive:
            existing.status = JobStatus.ACTIVE.value
            existing.inactive_at = None
            existing.updated_at = run_at
            reactivated += 1

        if _content_changed(existing, job_input):
            _apply_content(existing, job_input)
            existing.updated_at = run_at
            updated += 1
        else:
            unchanged += 1

    deactivated = 0
    if sync_mode == SyncMode.FULL_SNAPSHOT and seen_ids:
        deactivated = _deactivate_missing(session, provider, seen_ids, run_at)
    elif sync_mode == SyncMode.FULL_SNAPSHOT:
        deactivated = _deactivate_all_active(session, provider, run_at)

    session.flush()
    return UpsertCounts(
        created=created,
        updated=updated,
        unchanged=unchanged,
        reactivated=reactivated,
        deactivated=deactivated,
    )


def _job_from_input(job_input: NormalizedJobInput, run_at: datetime) -> Job:
    return Job(
        provider=job_input.provider,
        provider_job_id=job_input.provider_job_id,
        raw_payload=job_input.raw_payload,
        title=job_input.title,
        company=job_input.company,
        description=job_input.description,
        employment_type=job_input.employment_type.value,
        remote_type=job_input.remote_type.value,
        location_text=job_input.location_text,
        city=job_input.city,
        region=job_input.region,
        country_code=job_input.country_code,
        eligible_country_codes=job_input.eligible_country_codes,
        salary_min=job_input.salary_min,
        salary_max=job_input.salary_max,
        salary_currency=job_input.salary_currency,
        salary_period=(
            job_input.salary_period.value if job_input.salary_period else None
        ),
        salary_min_annual=job_input.salary_min_annual,
        salary_max_annual=job_input.salary_max_annual,
        job_url=str(job_input.job_url),
        apply_url=str(job_input.apply_url) if job_input.apply_url else None,
        status=JobStatus.ACTIVE.value,
        posted_at=job_input.posted_at,
        discovered_at=run_at,
        last_seen_at=run_at,
        updated_at=run_at,
        inactive_at=None,
    )


def _apply_content(job: Job, job_input: NormalizedJobInput) -> None:
    job.raw_payload = job_input.raw_payload
    job.title = job_input.title
    job.company = job_input.company
    job.description = job_input.description
    job.employment_type = job_input.employment_type.value
    job.remote_type = job_input.remote_type.value
    job.location_text = job_input.location_text
    job.city = job_input.city
    job.region = job_input.region
    job.country_code = job_input.country_code
    job.eligible_country_codes = job_input.eligible_country_codes
    job.salary_min = job_input.salary_min
    job.salary_max = job_input.salary_max
    job.salary_currency = job_input.salary_currency
    job.salary_period = (
        job_input.salary_period.value if job_input.salary_period else None
    )
    job.salary_min_annual = job_input.salary_min_annual
    job.salary_max_annual = job_input.salary_max_annual
    job.job_url = str(job_input.job_url)
    job.apply_url = str(job_input.apply_url) if job_input.apply_url else None
    job.posted_at = job_input.posted_at


def _content_snapshot(job: Job | NormalizedJobInput) -> dict[str, Any]:
    if isinstance(job, NormalizedJobInput):
        return {
            "raw_payload": _json_key(job.raw_payload),
            "title": job.title,
            "company": job.company,
            "description": job.description,
            "employment_type": job.employment_type.value,
            "remote_type": job.remote_type.value,
            "location_text": job.location_text,
            "city": job.city,
            "region": job.region,
            "country_code": job.country_code,
            "eligible_country_codes": job.eligible_country_codes,
            "salary_min": _decimal_key(job.salary_min),
            "salary_max": _decimal_key(job.salary_max),
            "salary_currency": job.salary_currency,
            "salary_period": (job.salary_period.value if job.salary_period else None),
            "salary_min_annual": _decimal_key(job.salary_min_annual),
            "salary_max_annual": _decimal_key(job.salary_max_annual),
            "job_url": str(job.job_url),
            "apply_url": str(job.apply_url) if job.apply_url else None,
            "posted_at": _datetime_key(job.posted_at),
        }
    return {
        "raw_payload": _json_key(job.raw_payload),
        "title": job.title,
        "company": job.company,
        "description": job.description,
        "employment_type": job.employment_type,
        "remote_type": job.remote_type,
        "location_text": job.location_text,
        "city": job.city,
        "region": job.region,
        "country_code": job.country_code,
        "eligible_country_codes": job.eligible_country_codes,
        "salary_min": _decimal_key(job.salary_min),
        "salary_max": _decimal_key(job.salary_max),
        "salary_currency": job.salary_currency,
        "salary_period": job.salary_period,
        "salary_min_annual": _decimal_key(job.salary_min_annual),
        "salary_max_annual": _decimal_key(job.salary_max_annual),
        "job_url": job.job_url,
        "apply_url": job.apply_url,
        "posted_at": _datetime_key(job.posted_at),
    }


def _content_changed(job: Job, job_input: NormalizedJobInput) -> bool:
    return _content_snapshot(job) != _content_snapshot(job_input)


def _json_key(value: dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def _decimal_key(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value, "f")


def _datetime_key(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _deactivate_missing(
    session: Session,
    provider: str,
    seen_ids: list[str],
    run_at: datetime,
) -> int:
    result = session.execute(
        update(Job)
        .where(
            Job.provider == provider,
            Job.status == JobStatus.ACTIVE.value,
            Job.provider_job_id.notin_(seen_ids),
        )
        .values(
            status=JobStatus.INACTIVE.value,
            inactive_at=run_at,
            updated_at=run_at,
        )
    )
    return result.rowcount or 0


def _deactivate_all_active(
    session: Session,
    provider: str,
    run_at: datetime,
) -> int:
    result = session.execute(
        update(Job)
        .where(
            Job.provider == provider,
            Job.status == JobStatus.ACTIVE.value,
        )
        .values(
            status=JobStatus.INACTIVE.value,
            inactive_at=run_at,
            updated_at=run_at,
        )
    )
    return result.rowcount or 0


__all__ = ["UpsertCounts", "apply_jobs"]
