"""Integration tests for ingestion upsert and lifecycle logic."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from jobs_back.ingestion.upsert import apply_jobs
from jobs_back.models import Job
from jobs_back.models.enums import JobStatus, SyncMode
from tests.helpers.fake_adapters import make_job_input


def _seed_job(
    db_session: Session,
    *,
    provider: str = "fake",
    provider_job_id: str = "job-1",
    status: JobStatus = JobStatus.ACTIVE,
    discovered_at: datetime | None = None,
    updated_at: datetime | None = None,
    **overrides: object,
) -> Job:
    run_at = datetime.now(tz=UTC)
    job = Job(
        id=uuid.uuid4(),
        provider=provider,
        provider_job_id=provider_job_id,
        raw_payload={"id": provider_job_id},
        title="Old Title",
        company="Acme",
        employment_type="unspecified",
        remote_type="unspecified",
        job_url="https://example.com/jobs/1",
        status=status.value,
        discovered_at=discovered_at or run_at,
        last_seen_at=run_at,
        updated_at=updated_at or run_at,
        inactive_at=run_at if status == JobStatus.INACTIVE else None,
    )
    for key, value in overrides.items():
        setattr(job, key, value)
    db_session.add(job)
    db_session.flush()
    return job


def test_create_job_on_first_seen(db_session: Session) -> None:
    run_at = datetime.now(tz=UTC)
    job_input = make_job_input(provider_job_id="new-1")
    counts = apply_jobs(
        db_session,
        provider="fake",
        jobs=[job_input],
        run_at=run_at,
        sync_mode=SyncMode.FULL_SNAPSHOT,
    )
    assert counts.created == 1
    loaded = db_session.execute(
        select(Job).where(Job.provider_job_id == "new-1")
    ).scalar_one()
    assert loaded.status == JobStatus.ACTIVE.value
    assert loaded.discovered_at == run_at
    assert loaded.last_seen_at == run_at


def test_update_changes_content_and_updated_at(db_session: Session) -> None:
    run_at = datetime.now(tz=UTC)
    old_updated = run_at - timedelta(days=1)
    existing = _seed_job(
        db_session,
        provider_job_id="job-1",
        updated_at=old_updated,
    )
    job_input = make_job_input(
        provider_job_id="job-1",
        title="New Title",
    )
    counts = apply_jobs(
        db_session,
        provider="fake",
        jobs=[job_input],
        run_at=run_at,
        sync_mode=SyncMode.INCREMENTAL,
    )
    assert counts.updated == 1
    assert counts.unchanged == 0
    db_session.refresh(existing)
    assert existing.title == "New Title"
    assert existing.updated_at == run_at
    assert existing.discovered_at != run_at


def test_unchanged_preserves_updated_at(db_session: Session) -> None:
    run_at = datetime.now(tz=UTC)
    old_updated = run_at - timedelta(days=2)
    existing = _seed_job(
        db_session,
        provider_job_id="job-1",
        title="Same Title",
        updated_at=old_updated,
    )
    job_input = make_job_input(
        provider_job_id="job-1",
        title="Same Title",
    )
    counts = apply_jobs(
        db_session,
        provider="fake",
        jobs=[job_input],
        run_at=run_at,
        sync_mode=SyncMode.INCREMENTAL,
    )
    assert counts.unchanged == 1
    db_session.refresh(existing)
    assert existing.updated_at == old_updated
    assert existing.last_seen_at == run_at


def test_reactivation_preserves_discovered_at(db_session: Session) -> None:
    run_at = datetime.now(tz=UTC)
    discovered = run_at - timedelta(days=10)
    existing = _seed_job(
        db_session,
        provider_job_id="job-1",
        status=JobStatus.INACTIVE,
        discovered_at=discovered,
    )
    job_input = make_job_input(provider_job_id="job-1")
    counts = apply_jobs(
        db_session,
        provider="fake",
        jobs=[job_input],
        run_at=run_at,
        sync_mode=SyncMode.INCREMENTAL,
    )
    assert counts.reactivated == 1
    db_session.refresh(existing)
    assert existing.status == JobStatus.ACTIVE.value
    assert existing.inactive_at is None
    assert existing.discovered_at == discovered


def test_full_snapshot_deactivates_missing_jobs(db_session: Session) -> None:
    run_at = datetime.now(tz=UTC)
    seen = _seed_job(db_session, provider_job_id="seen-1")
    missing = _seed_job(db_session, provider_job_id="missing-1")
    job_input = make_job_input(provider_job_id="seen-1")
    counts = apply_jobs(
        db_session,
        provider="fake",
        jobs=[job_input],
        run_at=run_at,
        sync_mode=SyncMode.FULL_SNAPSHOT,
    )
    assert counts.deactivated == 1
    db_session.refresh(seen)
    db_session.refresh(missing)
    assert seen.status == JobStatus.ACTIVE.value
    assert missing.status == JobStatus.INACTIVE.value
    assert missing.inactive_at == run_at


def test_incremental_does_not_deactivate_missing_jobs(db_session: Session) -> None:
    run_at = datetime.now(tz=UTC)
    missing = _seed_job(db_session, provider_job_id="missing-1")
    job_input = make_job_input(provider_job_id="other-1")
    counts = apply_jobs(
        db_session,
        provider="fake",
        jobs=[job_input],
        run_at=run_at,
        sync_mode=SyncMode.INCREMENTAL,
    )
    assert counts.deactivated == 0
    db_session.refresh(missing)
    assert missing.status == JobStatus.ACTIVE.value


def test_full_snapshot_empty_result_deactivates_all_active(db_session: Session) -> None:
    run_at = datetime.now(tz=UTC)
    job = _seed_job(db_session, provider_job_id="job-1")
    counts = apply_jobs(
        db_session,
        provider="fake",
        jobs=[],
        run_at=run_at,
        sync_mode=SyncMode.FULL_SNAPSHOT,
    )
    assert counts.deactivated == 1
    db_session.refresh(job)
    assert job.status == JobStatus.INACTIVE.value
