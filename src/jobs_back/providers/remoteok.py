from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import httpx
from pydantic import ValidationError

from jobs_back.providers.himalayas import _first, _money, _timestamp
from jobs_back.providers.protocol import ProviderPageBatch
from jobs_back.providers.sanitize import strip_html
from jobs_back.schemas.discovery import JobResult, SearchFilters

logger = logging.getLogger(__name__)

ATTRIBUTION_URL = "https://remoteok.com"
ATTRIBUTION_TEXT = (
    "This job listing is provided by Remote OK. "
    f"Please link back to {ATTRIBUTION_URL} when displaying this listing."
)


def _is_legal_notice(item: dict[str, Any]) -> bool:
    if "legal" in item:
        return True
    if "position" not in item and "company" not in item:
        return True
    return False


def normalize_job(item: dict[str, Any]) -> JobResult | None:
    if _is_legal_notice(item):
        return None
    job_id = _first(item, "id", "slug")
    title = _first(item, "position", "title")
    if job_id is None or not title:
        logger.debug("Skipping malformed RemoteOK row without id/title")
        return None
    job_id = str(job_id)
    url = _first(item, "url", "apply_url")
    if url is None:
        url = f"https://remoteok.com/remote-jobs/{job_id}"
    apply_url = _first(item, "apply_url", "url") or url
    tags = item.get("tags") or []
    seniority = None
    if isinstance(tags, list) and tags:
        seniority = ", ".join(str(tag) for tag in tags[:5])
    salary_min = _money(_first(item, "salary_min"), "annual")
    salary_max = _money(_first(item, "salary_max"), "annual")
    if salary_min is None and salary_max is not None:
        salary_min = salary_max
    if salary_max is None and salary_min is not None:
        salary_max = salary_min
    raw_description = _first(item, "description")
    payload = dict(item)
    payload["attribution_text"] = ATTRIBUTION_TEXT
    payload["attribution_url"] = ATTRIBUTION_URL
    try:
        return JobResult(
            provider="remoteok",
            provider_job_id=job_id,
            title=str(title),
            company=str(_first(item, "company", default="Unknown company")),
            description=strip_html(str(raw_description) if raw_description else None),
            location_text=str(_first(item, "location", default="Remote")),
            employment_type="unspecified",
            seniority=seniority,
            salary_min_annual=salary_min,
            salary_max_annual=salary_max,
            salary_currency=_first(item, "salary_currency", "currency") or "USD",
            job_url=str(url),
            apply_url=str(apply_url),
            company_logo_url=_first(item, "company_logo", "logo") or None,
            posted_at=_timestamp(_first(item, "epoch", "date")),
            provider_payload=payload,
        )
    except ValidationError:
        logger.debug("Skipping unusable RemoteOK row %s", job_id)
        return None


class RemoteOKProvider:
    key = "remoteok"

    def __init__(
        self,
        *,
        timeout: float = 20,
        batch_size: int = 100,
        max_retries: int = 3,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url="https://remoteok.com",
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": "JobScout/1.0"},
        )
        self._batch_size = max(1, batch_size)
        self._max_retries = max_retries

    async def close(self) -> None:
        await self._client.aclose()

    @staticmethod
    def _retry_delay(response: httpx.Response | None, attempt: int) -> float:
        if response is not None:
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                try:
                    return min(float(retry_after), 8.0)
                except ValueError:
                    try:
                        parsed = parsedate_to_datetime(retry_after)
                        if parsed.tzinfo is None:
                            parsed = parsed.replace(tzinfo=UTC)
                        delay = (parsed - datetime.now(UTC)).total_seconds()
                        return min(max(delay, 0.0), 8.0)
                    except (TypeError, ValueError):
                        pass
        return min(0.5 * (2**attempt), 8.0)

    def _params(self, filters: SearchFilters) -> dict[str, str]:
        params: dict[str, str] = {}
        if filters.query:
            params["tags"] = filters.query.replace(" ", ",")
        return params

    async def _request(
        self, filters: SearchFilters
    ) -> tuple[list[Any] | None, str | None]:
        last_warning: str | None = None
        for attempt in range(self._max_retries):
            response: httpx.Response | None = None
            try:
                response = await self._client.get("/api", params=self._params(filters))
                if response.status_code == 429 or response.status_code >= 500:
                    last_warning = f"RemoteOK returned {response.status_code}"
                    if attempt + 1 < self._max_retries:
                        await asyncio.sleep(self._retry_delay(response, attempt))
                        continue
                    return None, last_warning
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, list):
                    return None, "RemoteOK payload was not a list"
                return payload, None
            except httpx.TimeoutException:
                last_warning = "RemoteOK request timed out"
                if attempt + 1 < self._max_retries:
                    await asyncio.sleep(self._retry_delay(response, attempt))
                    continue
            except httpx.HTTPError:
                last_warning = "RemoteOK request failed"
                if attempt + 1 < self._max_retries:
                    await asyncio.sleep(self._retry_delay(response, attempt))
                    continue
        return None, last_warning

    async def pages(self, filters: SearchFilters) -> AsyncIterator[ProviderPageBatch]:
        payload, warning = await self._request(filters)
        if payload is None:
            yield ProviderPageBatch(
                items=[],
                page=1,
                total_pages=1,
                warnings=(warning or "RemoteOK request failed",),
            )
            return

        normalized: list[JobResult] = []
        truncated = False
        for item in payload:
            if not isinstance(item, dict):
                continue
            if len(normalized) >= self._batch_size:
                truncated = True
                break
            job = normalize_job(item)
            if job is not None:
                normalized.append(job)

        if not normalized:
            yield ProviderPageBatch(
                items=[],
                page=1,
                total_pages=1,
                warnings=(warning or "RemoteOK returned no usable jobs",),
            )
            return

        total_pages = max(
            1,
            (len(normalized) + self._batch_size - 1) // self._batch_size,
        )
        for index in range(total_pages):
            start = index * self._batch_size
            end = start + self._batch_size
            yield ProviderPageBatch(
                items=normalized[start:end],
                page=index + 1,
                total_pages=total_pages,
                warnings=(f"results truncated at {self._batch_size}",)
                if truncated and index == 0
                else (),
            )
