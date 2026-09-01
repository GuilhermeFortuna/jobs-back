"""Profile library save helpers for deduplicated snapshots."""

from __future__ import annotations

from jobs_back.normalization.dedup import derive_dedup_key
from jobs_back.schemas.discovery import AlternateSource, JobResult


def alternate_sources_payload(result: JobResult) -> list[dict[str, object]]:
    return [source.model_dump(mode="json") for source in result.alternate_sources]


def append_alternate_source(
    alternates: list[dict[str, object]],
    result: JobResult,
) -> list[dict[str, object]]:
    source = AlternateSource(
        provider=result.provider,
        provider_job_id=result.provider_job_id,
        job_url=result.job_url,
        apply_url=result.apply_url,
    ).model_dump(mode="json")
    identity = (source["provider"], source["provider_job_id"])
    if any(
        (item["provider"], item["provider_job_id"]) == identity for item in alternates
    ):
        return alternates
    return [*alternates, source]


def snapshot_dedup_key(result: JobResult) -> str:
    return derive_dedup_key(result)
