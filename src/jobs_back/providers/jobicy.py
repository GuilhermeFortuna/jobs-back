from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal
from email.utils import parsedate_to_datetime
from typing import Any

import httpx
from pydantic import ValidationError

from jobs_back.providers.himalayas import _first, _timestamp
from jobs_back.providers.protocol import ProviderPageBatch
from jobs_back.providers.sanitize import strip_html
from jobs_back.schemas.discovery import JobResult, SearchFilters

logger = logging.getLogger(__name__)

# Observed per-request cap from https://jobicy.com/api/v2/remote-jobs
RESULT_CAP = 50
API_BASE = "https://jobicy.com/api/v2"

EMPLOYMENT_MAP = {
    "full-time": "full_time",
    "full time": "full_time",
    "part-time": "part_time",
    "part time": "part_time",
    "contract": "contract",
    "internship": "internship",
    "freelance": "contract",
}


def _annual_salary(amount: Any) -> Decimal | None:
    if amount in (None, ""):
        return None
    try:
        return Decimal(str(amount))
    except (TypeError, ValueError):
        return None


def normalize_job(item: dict[str, Any]) -> JobResult | None:
    job_id = _first(item, "id", "jobSlug")
    title = _first(item, "jobTitle", "title")
    if job_id is None or not title:
        logger.debug("Skipping malformed Jobicy row without id/title")
        return None
    job_id = str(job_id)
    url = _first(item, "url")
    if url is None:
        url = f"https://jobicy.com/jobs/{job_id}"
    job_type = _first(item, "jobType", default=[])
    employment = "unspecified"
    if isinstance(job_type, list) and job_type:
        employment = EMPLOYMENT_MAP.get(str(job_type[0]).lower(), "unspecified")
    elif isinstance(job_type, str):
        employment = EMPLOYMENT_MAP.get(job_type.lower(), "unspecified")
    seniority = _first(item, "jobLevel")
    location = _first(item, "jobGeo", "location")
    period = str(_first(item, "salaryPeriod", default="yearly")).lower()
    salary_min = _annual_salary(_first(item, "salaryMin"))
    salary_max = _annual_salary(_first(item, "salaryMax"))
    if period in {"monthly"} and salary_min is not None:
        salary_min *= 12
    if period in {"monthly"} and salary_max is not None:
        salary_max *= 12
    raw_description = _first(item, "jobDescription", "jobExcerpt")
    company = str(_first(item, "companyName", "company", default="Unknown company"))
    try:
        return JobResult(
            provider="jobicy",
            provider_job_id=job_id,
            title=str(title),
            company=company,
            description=strip_html(str(raw_description) if raw_description else None),
            location_text=str(location) if location else "Remote",
            employment_type=employment,
            seniority=str(seniority) if seniority is not None else None,
            salary_min_annual=salary_min,
            salary_max_annual=salary_max,
            salary_currency=_first(item, "salaryCurrency", "currency"),
            job_url=str(url),
            apply_url=str(url),
            company_logo_url=_first(item, "companyLogo", "logo") or None,
            posted_at=_timestamp(_first(item, "pubDate", "publishedAt")),
            provider_payload=item,
        )
    except ValidationError:
        logger.debug("Skipping unusable Jobicy row %s", job_id)
        return None


class JobicyProvider:
    key = "jobicy"

    def __init__(
        self,
        *,
        timeout: float = 20,
        max_retries: int = 3,
        result_cap: int = RESULT_CAP,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=API_BASE,
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": "JobScout/1.0"},
        )
        self._max_retries = max_retries
        self._result_cap = max(1, result_cap)

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

    def _params(self, filters: SearchFilters) -> dict[str, str | int]:
        params: dict[str, str | int] = {"count": self._result_cap}
        if filters.country:
            params["geo"] = filters.country
        if filters.query:
            params["tag"] = filters.query
        return params

    def _is_broad_search(self, filters: SearchFilters) -> bool:
        return (
            not filters.query and not filters.country and filters.worldwide is not False
        )

    async def _request(
        self, filters: SearchFilters
    ) -> tuple[dict[str, Any] | None, str | None]:
        last_warning: str | None = None
        for attempt in range(self._max_retries):
            response: httpx.Response | None = None
            try:
                response = await self._client.get(
                    "/remote-jobs",
                    params=self._params(filters),
                )
                if response.status_code == 429 or response.status_code >= 500:
                    last_warning = f"Jobicy returned {response.status_code}"
                    if attempt + 1 < self._max_retries:
                        await asyncio.sleep(self._retry_delay(response, attempt))
                        continue
                    return None, last_warning
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    return None, "Jobicy payload was not an object"
                return payload, None
            except httpx.TimeoutException:
                last_warning = "Jobicy request timed out"
                if attempt + 1 < self._max_retries:
                    await asyncio.sleep(self._retry_delay(response, attempt))
                    continue
            except httpx.HTTPError:
                last_warning = "Jobicy request failed"
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
                warnings=(warning or "Jobicy request failed",),
            )
            return

        raw_jobs = payload.get("jobs", [])
        if not isinstance(raw_jobs, list):
            yield ProviderPageBatch(
                items=[],
                page=1,
                total_pages=1,
                warnings=("Jobicy payload did not contain jobs",),
            )
            return

        normalized: list[JobResult] = []
        for item in raw_jobs:
            if not isinstance(item, dict):
                continue
            job = normalize_job(item)
            if job is not None:
                normalized.append(job)

        normalized = normalized[: self._result_cap]

        warnings: list[str] = []
        if warning:
            warnings.append(warning)
        if self._is_broad_search(filters) and len(raw_jobs) >= self._result_cap:
            warnings.append(f"results truncated at {self._result_cap}")

        if not normalized:
            yield ProviderPageBatch(
                items=[],
                page=1,
                total_pages=1,
                warnings=tuple(warnings or ("Jobicy returned no usable jobs",)),
            )
            return

        yield ProviderPageBatch(
            items=normalized,
            page=1,
            total_pages=1,
            warnings=tuple(warnings),
        )
