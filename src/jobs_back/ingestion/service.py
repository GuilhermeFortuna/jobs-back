"""Ingestion service orchestrating sync runs."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from jobs_back.config import Settings
from jobs_back.ingestion.exceptions import (
    IngestionError,
    ProviderLockError,
    sanitize_error,
)
from jobs_back.ingestion.fetch import collect_jobs
from jobs_back.ingestion.lock import ProviderLockNotAcquired, provider_advisory_lock
from jobs_back.ingestion.protocol import ProviderAdapter
from jobs_back.ingestion.registry import resolve
from jobs_back.ingestion.upsert import UpsertCounts, apply_jobs
from jobs_back.models.enums import SyncRunStatus, SyncTrigger
from jobs_back.models.sync_run import SyncRun

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SyncRunSuccess:
    run_id: uuid.UUID
    fetched: int
    created: int
    updated: int
    unchanged: int
    reactivated: int
    deactivated: int


@dataclass(frozen=True)
class SyncRunFailure:
    run_id: uuid.UUID
    error_code: str
    error_message: str


@dataclass(frozen=True)
class SetupFailure:
    error_code: str
    error_message: str


@dataclass(frozen=True)
class LockContention:
    error_code: str
    error_message: str


SyncResult = SyncRunSuccess | SyncRunFailure | SetupFailure | LockContention


class IngestionService:
    def __init__(
        self,
        settings: Settings,
        *,
        engine: Engine | None = None,
        session_factory: sessionmaker[Session] | None = None,
    ) -> None:
        self._settings = settings
        self._engine = engine or create_engine(
            settings.database_url,
            pool_pre_ping=True,
        )
        self._session_factory = session_factory or sessionmaker(
            bind=self._engine,
            autocommit=False,
            autoflush=False,
        )

    async def run_sync(self, provider_key: str) -> SyncResult:
        try:
            adapter = resolve(provider_key, self._settings)
        except IngestionError as exc:
            return SetupFailure(exc.error_code, exc.operator_message)

        try:
            with provider_advisory_lock(self._engine, provider_key):
                return await self._run_with_lock(adapter)
        except ProviderLockNotAcquired:
            return LockContention(
                ProviderLockError.error_code,
                ProviderLockError.operator_message,
            )

    async def _run_with_lock(self, adapter: ProviderAdapter) -> SyncResult:
        run_id = uuid.uuid4()
        started_at = datetime.now(tz=UTC)
        sync_run = SyncRun(
            id=run_id,
            provider=adapter.provider_key,
            trigger=SyncTrigger.MANUAL.value,
            sync_mode=adapter.sync_mode.value,
            status=SyncRunStatus.RUNNING.value,
            started_at=started_at,
        )

        session = self._session_factory()
        try:
            session.add(sync_run)
            session.commit()
        except Exception as exc:
            session.rollback()
            session.close()
            logger.exception("Failed to create running sync record %s", run_id)
            return SetupFailure(*sanitize_error(exc))
        finally:
            if session.is_active:
                session.close()

        try:
            jobs = await collect_jobs(adapter)
        except Exception as exc:
            error_code, error_message = sanitize_error(exc)
            self._mark_run_failed(run_id, error_code, error_message)
            return SyncRunFailure(run_id, error_code, error_message)

        session = self._session_factory()
        try:
            counts = apply_jobs(
                session,
                provider=adapter.provider_key,
                jobs=jobs,
                run_at=started_at,
                sync_mode=adapter.sync_mode,
            )
            self._mark_run_succeeded(
                session,
                run_id,
                fetched=len(jobs),
                counts=counts,
            )
            session.commit()
        except Exception as exc:
            session.rollback()
            session.close()
            error_code, error_message = sanitize_error(exc)
            self._mark_run_failed(run_id, error_code, error_message)
            return SyncRunFailure(run_id, error_code, error_message)
        else:
            session.close()

        return SyncRunSuccess(
            run_id=run_id,
            fetched=len(jobs),
            created=counts.created,
            updated=counts.updated,
            unchanged=counts.unchanged,
            reactivated=counts.reactivated,
            deactivated=counts.deactivated,
        )

    def _mark_run_succeeded(
        self,
        session: Session,
        run_id: uuid.UUID,
        *,
        fetched: int,
        counts: UpsertCounts,
    ) -> None:
        run = session.get(SyncRun, run_id)
        if run is None:
            msg = f"Sync run not found: {run_id}"
            raise RuntimeError(msg)
        run.status = SyncRunStatus.SUCCEEDED.value
        run.finished_at = datetime.now(tz=UTC)
        run.fetched = fetched
        run.created = counts.created
        run.updated = counts.updated
        run.unchanged = counts.unchanged
        run.reactivated = counts.reactivated
        run.deactivated = counts.deactivated

    def _mark_run_failed(
        self,
        run_id: uuid.UUID,
        error_code: str,
        error_message: str,
    ) -> None:
        session = self._session_factory()
        try:
            run = session.get(SyncRun, run_id)
            if run is None:
                logger.error(
                    "Cannot mark missing sync run failed: %s",
                    run_id,
                )
                return
            run.status = SyncRunStatus.FAILED.value
            run.finished_at = datetime.now(tz=UTC)
            run.error_code = error_code
            run.error_message = error_message
            session.commit()
        except Exception:
            session.rollback()
            logger.exception(
                "Failed to record sync failure for run %s",
                run_id,
            )
        finally:
            session.close()


__all__ = [
    "IngestionService",
    "LockContention",
    "SetupFailure",
    "SyncResult",
    "SyncRunFailure",
    "SyncRunSuccess",
]
