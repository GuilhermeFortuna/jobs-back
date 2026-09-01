"""Fake provider adapters for ingestion tests."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field

from jobs_back.config import Settings
from jobs_back.ingestion.exceptions import AdapterConfigurationError
from jobs_back.ingestion.protocol import ProviderAdapter
from jobs_back.ingestion.registry import register
from jobs_back.models.enums import SyncMode
from jobs_back.schemas.job import NormalizedJobInput


@dataclass
class FakeAdapter(ProviderAdapter):
    provider_key: str
    sync_mode: SyncMode
    jobs: list[NormalizedJobInput] = field(default_factory=list)
    fetch_error: BaseException | None = None

    def iter_jobs(self) -> AsyncIterator[NormalizedJobInput]:
        return _iter_jobs(self.jobs, self.fetch_error)


async def _iter_jobs(
    jobs: list[NormalizedJobInput],
    fetch_error: BaseException | None,
) -> AsyncIterator[NormalizedJobInput]:
    if fetch_error is not None:
        raise fetch_error
    for job in jobs:
        yield job


def make_job_input(
    *,
    provider: str = "fake",
    provider_job_id: str = "job-1",
    title: str = "Software Engineer",
    company: str = "Acme",
    **overrides: object,
) -> NormalizedJobInput:
    data: dict[str, object] = {
        "provider": provider,
        "provider_job_id": provider_job_id,
        "raw_payload": {"id": provider_job_id},
        "title": title,
        "company": company,
        "job_url": "https://example.com/jobs/1",
    }
    data.update(overrides)
    return NormalizedJobInput.model_validate(data)


def register_fake_adapter(
    provider_key: str,
    *,
    sync_mode: SyncMode = SyncMode.FULL_SNAPSHOT,
    jobs: list[NormalizedJobInput] | None = None,
    fetch_error: BaseException | None = None,
    require_config_key: str | None = None,
) -> None:
    """Register a fake adapter factory for tests."""

    def factory(settings: Settings) -> ProviderAdapter:
        if require_config_key is not None:
            config = settings.provider_config.get(provider_key)
            if not config or require_config_key not in config:
                raise AdapterConfigurationError(
                    f"Missing config for provider {provider_key!r}",
                )
        return FakeAdapter(
            provider_key=provider_key,
            sync_mode=sync_mode,
            jobs=jobs or [],
            fetch_error=fetch_error,
        )

    register(provider_key, factory)


def register_callable_adapter(
    provider_key: str,
    factory_fn: Callable[[Settings], ProviderAdapter],
) -> None:
    register(provider_key, factory_fn)
