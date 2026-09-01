"""Fetch and validate adapter job results before persistence."""

from __future__ import annotations

from collections.abc import AsyncIterator

from jobs_back.ingestion.exceptions import (
    AdapterProviderMismatchError,
    DuplicateIdentityError,
)
from jobs_back.ingestion.protocol import ProviderAdapter
from jobs_back.schemas.job import NormalizedJobInput


async def collect_jobs(adapter: ProviderAdapter) -> list[NormalizedJobInput]:
    """Materialize adapter output and reject duplicate identities."""
    jobs: list[NormalizedJobInput] = []
    seen: set[tuple[str, str]] = set()
    async for job in _async_iter(adapter.iter_jobs()):
        if job.provider != adapter.provider_key:
            raise AdapterProviderMismatchError(
                "Adapter job provider does not match adapter.provider_key",
            )
        identity = (job.provider, job.provider_job_id)
        if identity in seen:
            raise DuplicateIdentityError(
                f"Duplicate provider identity: {identity!r}",
            )
        seen.add(identity)
        jobs.append(job)
    return jobs


async def _async_iter(iterator: AsyncIterator[NormalizedJobInput]):
    async for item in iterator:
        yield item


__all__ = ["collect_jobs"]
