"""End-to-end tests for the ingestion service."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from jobs_back.config import Settings
from jobs_back.ingestion.exceptions import AdapterTransportError
from jobs_back.ingestion.registry import clear_registry
from jobs_back.ingestion.service import (
    IngestionService,
    SetupFailure,
    SyncRunFailure,
    SyncRunSuccess,
)
from jobs_back.models import Job, SyncRun
from jobs_back.models.enums import JobStatus, SyncMode, SyncRunStatus
from tests.helpers.fake_adapters import make_job_input, register_fake_adapter


@pytest.fixture(autouse=True)
def _clean_registry() -> None:
    clear_registry()
    yield
    clear_registry()


@pytest.fixture
def ingestion_service(committed_engine) -> IngestionService:
    settings = Settings()
    session_factory = sessionmaker(
        bind=committed_engine,
        autocommit=False,
        autoflush=False,
    )
    return IngestionService(
        settings,
        engine=committed_engine,
        session_factory=session_factory,
    )


def _run(service: IngestionService, provider: str):
    return asyncio.run(service.run_sync(provider))


def test_successful_full_snapshot_creates_jobs(
    ingestion_service: IngestionService,
    committed_session: Session,
) -> None:
    register_fake_adapter(
        "fake-full",
        sync_mode=SyncMode.FULL_SNAPSHOT,
        jobs=[
            make_job_input(provider="fake-full", provider_job_id="a"),
            make_job_input(provider="fake-full", provider_job_id="b"),
        ],
    )
    result = _run(ingestion_service, "fake-full")
    assert isinstance(result, SyncRunSuccess)
    assert result.fetched == 2
    assert result.created == 2
    jobs = (
        committed_session.execute(select(Job).where(Job.provider == "fake-full"))
        .scalars()
        .all()
    )
    assert len(jobs) == 2


def test_rerun_updates_without_duplicates(
    ingestion_service: IngestionService,
    committed_session: Session,
) -> None:
    register_fake_adapter(
        "fake-rerun",
        jobs=[make_job_input(provider="fake-rerun", provider_job_id="same")],
    )
    first = _run(ingestion_service, "fake-rerun")
    assert isinstance(first, SyncRunSuccess)
    assert first.created == 1

    second = _run(ingestion_service, "fake-rerun")
    assert isinstance(second, SyncRunSuccess)
    assert second.created == 0
    assert second.unchanged == 1

    jobs = (
        committed_session.execute(select(Job).where(Job.provider == "fake-rerun"))
        .scalars()
        .all()
    )
    assert len(jobs) == 1
    assert jobs[0].id is not None


def test_full_snapshot_deactivates_missing(
    ingestion_service: IngestionService,
    committed_session: Session,
) -> None:
    run_at = datetime.now(tz=UTC)
    old_job = Job(
        id=uuid.uuid4(),
        provider="fake-snap",
        provider_job_id="old",
        raw_payload={"id": "old"},
        title="Old",
        company="Acme",
        employment_type="unspecified",
        remote_type="unspecified",
        job_url="https://example.com/old",
        status=JobStatus.ACTIVE.value,
        discovered_at=run_at,
        last_seen_at=run_at,
        updated_at=run_at,
    )
    committed_session.add(old_job)
    committed_session.commit()

    register_fake_adapter(
        "fake-snap",
        sync_mode=SyncMode.FULL_SNAPSHOT,
        jobs=[make_job_input(provider="fake-snap", provider_job_id="new")],
    )
    result = _run(ingestion_service, "fake-snap")
    assert isinstance(result, SyncRunSuccess)
    assert result.deactivated == 1

    committed_session.expire_all()
    old_loaded = committed_session.get(Job, old_job.id)
    assert old_loaded is not None
    assert old_loaded.status == JobStatus.INACTIVE.value


def test_incremental_does_not_deactivate(
    ingestion_service: IngestionService,
    committed_session: Session,
) -> None:
    run_at = datetime.now(tz=UTC)
    old_job = Job(
        id=uuid.uuid4(),
        provider="fake-inc",
        provider_job_id="stale",
        raw_payload={"id": "stale"},
        title="Stale",
        company="Acme",
        employment_type="unspecified",
        remote_type="unspecified",
        job_url="https://example.com/stale",
        status=JobStatus.ACTIVE.value,
        discovered_at=run_at,
        last_seen_at=run_at,
        updated_at=run_at,
    )
    committed_session.add(old_job)
    committed_session.commit()

    register_fake_adapter(
        "fake-inc",
        sync_mode=SyncMode.INCREMENTAL,
        jobs=[make_job_input(provider="fake-inc", provider_job_id="new")],
    )
    result = _run(ingestion_service, "fake-inc")
    assert isinstance(result, SyncRunSuccess)
    assert result.deactivated == 0

    committed_session.expire_all()
    stale = committed_session.get(Job, old_job.id)
    assert stale is not None
    assert stale.status == JobStatus.ACTIVE.value


def test_reactivation_preserves_discovered_at(
    ingestion_service: IngestionService,
    committed_session: Session,
) -> None:
    discovered = datetime.now(tz=UTC) - timedelta(days=30)
    run_at = datetime.now(tz=UTC)
    inactive_job = Job(
        id=uuid.uuid4(),
        provider="fake-react",
        provider_job_id="back",
        raw_payload={"id": "back"},
        title="Back",
        company="Acme",
        employment_type="unspecified",
        remote_type="unspecified",
        job_url="https://example.com/back",
        status=JobStatus.INACTIVE.value,
        discovered_at=discovered,
        last_seen_at=run_at,
        updated_at=run_at,
        inactive_at=run_at,
    )
    committed_session.add(inactive_job)
    committed_session.commit()

    register_fake_adapter(
        "fake-react",
        sync_mode=SyncMode.INCREMENTAL,
        jobs=[make_job_input(provider="fake-react", provider_job_id="back")],
    )
    result = _run(ingestion_service, "fake-react")
    assert isinstance(result, SyncRunSuccess)
    assert result.reactivated == 1

    committed_session.expire_all()
    loaded = committed_session.get(Job, inactive_job.id)
    assert loaded is not None
    assert loaded.status == JobStatus.ACTIVE.value
    assert loaded.discovered_at == discovered


def test_fetch_failure_leaves_jobs_unchanged(
    ingestion_service: IngestionService,
    committed_session: Session,
) -> None:
    run_at = datetime.now(tz=UTC)
    job = Job(
        id=uuid.uuid4(),
        provider="fake-fail",
        provider_job_id="keep",
        raw_payload={"id": "keep"},
        title="Keep",
        company="Acme",
        employment_type="unspecified",
        remote_type="unspecified",
        job_url="https://example.com/keep",
        status=JobStatus.ACTIVE.value,
        discovered_at=run_at,
        last_seen_at=run_at,
        updated_at=run_at,
    )
    committed_session.add(job)
    committed_session.commit()

    register_fake_adapter(
        "fake-fail",
        fetch_error=AdapterTransportError("network down"),
    )
    result = _run(ingestion_service, "fake-fail")
    assert isinstance(result, SyncRunFailure)

    committed_session.expire_all()
    loaded = committed_session.get(Job, job.id)
    assert loaded is not None
    assert loaded.title == "Keep"

    run = committed_session.get(SyncRun, result.run_id)
    assert run is not None
    assert run.status == SyncRunStatus.FAILED.value
    assert run.error_code == "adapter_transport_failed"


def test_duplicate_identity_fails_before_persistence(
    ingestion_service: IngestionService,
) -> None:
    duplicate = make_job_input(provider="fake-dup", provider_job_id="same")
    register_fake_adapter(
        "fake-dup",
        jobs=[duplicate, duplicate],
    )
    result = _run(ingestion_service, "fake-dup")
    assert isinstance(result, SyncRunFailure)
    assert result.error_code == "duplicate_provider_identity"


def test_unknown_provider_returns_setup_failure(
    ingestion_service: IngestionService,
) -> None:
    result = _run(ingestion_service, "missing")
    assert isinstance(result, SetupFailure)
    assert result.error_code == "unknown_provider"


def test_committed_running_record_can_exist_without_recovery(
    committed_session: Session,
) -> None:
    run = SyncRun(
        id=uuid.uuid4(),
        provider="orphan",
        trigger="manual",
        sync_mode=SyncMode.FULL_SNAPSHOT.value,
        status=SyncRunStatus.RUNNING.value,
        started_at=datetime.now(tz=UTC),
    )
    committed_session.add(run)
    committed_session.commit()
    loaded = committed_session.get(SyncRun, run.id)
    assert loaded is not None
    assert loaded.status == SyncRunStatus.RUNNING.value
    assert loaded.finished_at is None
