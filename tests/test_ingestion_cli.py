"""CLI tests for ingestion exit codes and output."""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
from sqlalchemy.orm import sessionmaker

from jobs_back.config import Settings
from jobs_back.ingestion.cli import main
from jobs_back.ingestion.exceptions import AdapterTransportError
from jobs_back.ingestion.registry import clear_registry, register
from jobs_back.ingestion.service import IngestionService
from jobs_back.models.enums import SyncMode
from tests.helpers.fake_adapters import (
    FakeAdapter,
    make_job_input,
    register_fake_adapter,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _clean_registry() -> None:
    clear_registry()
    yield
    clear_registry()


def test_cli_success_exit_code(committed_engine, capsys) -> None:
    register_fake_adapter(
        "cli-ok",
        jobs=[make_job_input(provider="cli-ok", provider_job_id="1")],
    )
    exit_code = main(["sync", "--provider", "cli-ok"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "run_id=" in captured.out
    assert "created=1" in captured.out


def test_cli_run_failure_exit_code(committed_engine, capsys) -> None:
    register_fake_adapter(
        "cli-fail",
        fetch_error=AdapterTransportError("boom"),
    )
    exit_code = main(["sync", "--provider", "cli-fail"])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "run_id=" in captured.out
    assert "error=adapter_transport_failed" in captured.out


def test_cli_unknown_provider_exit_code(capsys) -> None:
    exit_code = main(["sync", "--provider", "missing"])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "error=unknown_provider" in captured.out


def test_cli_lock_contention_exit_code(committed_engine, capsys) -> None:
    release = threading.Event()

    async def blocked_iter():
        release.wait(timeout=5)
        yield make_job_input(provider="cli-lock", provider_job_id="1")

    def factory(_):
        adapter = FakeAdapter(
            provider_key="cli-lock",
            sync_mode=SyncMode.FULL_SNAPSHOT,
        )
        adapter.iter_jobs = blocked_iter  # type: ignore[method-assign]
        return adapter

    register("cli-lock", factory)

    def hold_lock() -> None:
        service = IngestionService(
            Settings(),
            engine=committed_engine,
            session_factory=sessionmaker(
                bind=committed_engine,
                autocommit=False,
                autoflush=False,
            ),
        )
        asyncio.run(service.run_sync("cli-lock"))

    thread = threading.Thread(target=hold_lock)
    thread.start()
    time.sleep(0.2)
    exit_code = main(["sync", "--provider", "cli-lock"])
    release.set()
    thread.join(timeout=10)
    captured = capsys.readouterr()
    assert exit_code == 3
    assert "error=provider_locked" in captured.out


def test_subprocess_module_invocation_unknown_provider(database_url: str) -> None:
    env = {**os.environ, "DATABASE_URL": database_url}
    result = subprocess.run(
        [sys.executable, "-m", "jobs_back.ingestion", "sync", "--provider", "nope"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "error=unknown_provider" in result.stdout


def test_subprocess_invalid_args() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "jobs_back.ingestion"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
