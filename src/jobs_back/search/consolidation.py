"""Cross-provider duplicate consolidation helpers."""

from __future__ import annotations

from decimal import Decimal

from jobs_back.providers.registry import KNOWN_KEYS
from jobs_back.schemas.discovery import AlternateSource, JobResult

_PROVIDER_PRECEDENCE = {key: index for index, key in enumerate(KNOWN_KEYS)}


def _source_identity(item: JobResult) -> tuple[str, str]:
    return (item.provider, item.provider_job_id)


def to_alternate_source(item: JobResult) -> AlternateSource:
    return AlternateSource(
        provider=item.provider,
        provider_job_id=item.provider_job_id,
        job_url=item.job_url,
        apply_url=item.apply_url,
    )


def _compensation_score(item: JobResult) -> tuple[int, Decimal]:
    has_bounds = int(
        item.salary_min_annual is not None or item.salary_max_annual is not None
    )
    max_annual = item.salary_max_annual or item.salary_min_annual or Decimal(0)
    return (has_bounds, max_annual)


def source_richness(item: JobResult) -> tuple[int, Decimal, int, int, str, str]:
    compensation = _compensation_score(item)
    description_length = len(item.description or "")
    provider_rank = _PROVIDER_PRECEDENCE.get(item.provider, len(KNOWN_KEYS))
    provider, provider_job_id = _source_identity(item)
    return (
        compensation[0],
        compensation[1],
        description_length,
        -provider_rank,
        provider,
        provider_job_id,
    )


def pick_canonical(current: JobResult, incoming: JobResult) -> JobResult:
    if source_richness(incoming) > source_richness(current):
        return incoming
    return current


def _append_alternate(
    alternates: list[AlternateSource],
    item: JobResult,
    *,
    exclude: set[tuple[str, str]],
) -> list[AlternateSource]:
    identity = _source_identity(item)
    if identity in exclude:
        return alternates
    if any(
        (source.provider, source.provider_job_id) == identity for source in alternates
    ):
        return alternates
    return [*alternates, to_alternate_source(item)]


def _append_existing_alternate(
    alternates: list[AlternateSource],
    source: AlternateSource,
    *,
    exclude: set[tuple[str, str]],
) -> list[AlternateSource]:
    identity = (source.provider, source.provider_job_id)
    if identity in exclude:
        return alternates
    if any(
        (existing.provider, existing.provider_job_id) == identity
        for existing in alternates
    ):
        return alternates
    return [*alternates, source]


def merge_results(current: JobResult, incoming: JobResult) -> JobResult:
    canonical = pick_canonical(current, incoming)
    loser = (
        incoming
        if _source_identity(canonical) == _source_identity(current)
        else current
    )
    canonical_identity = {_source_identity(canonical)}
    alternates = list(canonical.alternate_sources)
    alternates = _append_alternate(alternates, loser, exclude=canonical_identity)
    for source in [*current.alternate_sources, *incoming.alternate_sources]:
        alternates = _append_existing_alternate(
            alternates,
            source,
            exclude=canonical_identity,
        )
    return canonical.model_copy(update={"alternate_sources": alternates})


def matches_source_identity(
    item: JobResult,
    provider: str,
    provider_job_id: str,
) -> bool:
    if item.provider == provider and item.provider_job_id == provider_job_id:
        return True
    return any(
        source.provider == provider and source.provider_job_id == provider_job_id
        for source in item.alternate_sources
    )
