"""Profile library save helpers for deduplicated snapshots."""

from __future__ import annotations

from jobs_back.normalization.dedup import derive_dedup_key
from jobs_back.schemas.discovery import JobResult


def alternate_sources_payload(result: JobResult) -> list[dict[str, object]]:
    return [source.model_dump(mode="json") for source in result.alternate_sources]


def merged_alternate_sources(
    existing_sources: list[dict[str, object]],
    existing_identity: dict[str, object],
    result: JobResult,
) -> list[dict[str, object]]:
    """Union of every source a consolidated row has ever carried.

    The incoming result becomes the canonical source, so the row's previous
    identity and both source lists are folded into the alternates. Sources are
    keyed by provider identity so repeated saves stay idempotent.
    """
    canonical = (result.provider, result.provider_job_id)
    merged: list[dict[str, object]] = []
    seen: set[tuple[object, object]] = {canonical}
    candidates = [
        *existing_sources,
        existing_identity,
        *alternate_sources_payload(result),
    ]
    for source in candidates:
        identity = (source["provider"], source["provider_job_id"])
        if identity in seen:
            continue
        seen.add(identity)
        merged.append(source)
    return merged


def snapshot_dedup_key(result: JobResult) -> str:
    return derive_dedup_key(result)
