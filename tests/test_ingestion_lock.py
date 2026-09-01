"""Tests for provider advisory lock behavior."""

from __future__ import annotations

import asyncio
import threading

import pytest
from sqlalchemy.orm import sessionmaker

from jobs_back.config import Settings
from jobs_back.ingestion.lock import (
    ProviderLockNotAcquired,
    provider_advisory_lock,
    provider_lock_key,
)
from jobs_back.ingestion.registry import clear_registry
from jobs_back.ingestion.service import IngestionService, LockContention, SyncRunSuccess
from jobs_back.models.enums import SyncMode
from tests.helpers.fake_adapters import FakeAdapter, make_job_input, register


@pytest.fixture(autouse=True)
def _clean_registry() -> None:
    clear_registry()
    yield
    clear_registry()


def test_provider_lock_key_is_deterministic() -> None:
    assert provider_lock_key("alpha") == provider_lock_key("alpha")
    assert provider_lock_key("alpha") != provider_lock_key("beta")


def test_advisory_lock_released_after_context(committed_engine) -> None:
    with provider_advisory_lock(committed_engine, "lock-test"):
        pass
    with provider_advisory_lock(committed_engine, "lock-test"):
        pass


def test_advisory_lock_contention_raises(committed_engine) -> None:
    with provider_advisory_lock(committed_engine, "contended"):
        with pytest.raises(ProviderLockNotAcquired):
            with provider_advisory_lock(committed_engine, "contended"):
                pass


def test_same_provider_sync_rejected_while_running(committed_engine) -> None:
    started = threading.Event()
    release = threading.Event()

    async def slow_iter():
        started.set()
        release.wait(timeout=5)
        yield make_job_input(provider="slow", provider_job_id="1")

    def factory(_: Settings) -> FakeAdapter:
        adapter = FakeAdapter(
            provider_key="slow",
            sync_mode=SyncMode.FULL_SNAPSHOT,
        )
        adapter.iter_jobs = slow_iter  # type: ignore[method-assign]
        return adapter

    register("slow", factory)
    settings = Settings()
    session_factory = sessionmaker(
        bind=committed_engine,
        autocommit=False,
        autoflush=False,
    )
    service = IngestionService(
        settings,
        engine=committed_engine,
        session_factory=session_factory,
    )

    first_result: list = []
    second_result: list = []

    def run_first() -> None:
        first_result.append(asyncio.run(service.run_sync("slow")))

    thread = threading.Thread(target=run_first)
    thread.start()
    assert started.wait(timeout=5)

    second_result.append(asyncio.run(service.run_sync("slow")))
    release.set()
    thread.join(timeout=10)

    assert len(first_result) == 1
    assert isinstance(first_result[0], SyncRunSuccess)
    assert len(second_result) == 1
    assert isinstance(second_result[0], LockContention)


def test_different_providers_can_run_independently(committed_engine) -> None:
    from tests.helpers.fake_adapters import register_fake_adapter

    register_fake_adapter(
        "provider-a",
        sync_mode=SyncMode.INCREMENTAL,
        jobs=[make_job_input(provider="provider-a", provider_job_id="a")],
    )
    register_fake_adapter(
        "provider-b",
        sync_mode=SyncMode.INCREMENTAL,
        jobs=[make_job_input(provider="provider-b", provider_job_id="b")],
    )
    settings = Settings()
    session_factory = sessionmaker(
        bind=committed_engine,
        autocommit=False,
        autoflush=False,
    )
    service = IngestionService(
        settings,
        engine=committed_engine,
        session_factory=session_factory,
    )

    result_a = asyncio.run(service.run_sync("provider-a"))
    result_b = asyncio.run(service.run_sync("provider-b"))
    assert isinstance(result_a, SyncRunSuccess)
    assert isinstance(result_b, SyncRunSuccess)
