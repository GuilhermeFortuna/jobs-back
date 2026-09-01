"""Tests for adapter job collection and duplicate detection."""

from __future__ import annotations

import pytest

from jobs_back.ingestion.exceptions import DuplicateIdentityError
from jobs_back.ingestion.fetch import collect_jobs
from jobs_back.models.enums import SyncMode
from tests.helpers.fake_adapters import FakeAdapter, make_job_input


@pytest.mark.asyncio
async def test_collect_jobs_returns_all_items() -> None:
    jobs = [
        make_job_input(provider_job_id="a"),
        make_job_input(provider_job_id="b"),
    ]
    adapter = FakeAdapter(
        provider_key="fake",
        sync_mode=SyncMode.FULL_SNAPSHOT,
        jobs=jobs,
    )
    collected = await collect_jobs(adapter)
    assert len(collected) == 2


@pytest.mark.asyncio
async def test_collect_jobs_rejects_duplicate_identities() -> None:
    duplicate = make_job_input(provider_job_id="dup")
    adapter = FakeAdapter(
        provider_key="fake",
        sync_mode=SyncMode.FULL_SNAPSHOT,
        jobs=[duplicate, duplicate],
    )
    with pytest.raises(DuplicateIdentityError):
        await collect_jobs(adapter)
