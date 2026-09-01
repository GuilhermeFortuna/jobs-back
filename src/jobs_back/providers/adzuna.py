from __future__ import annotations

import asyncio
import logging
import math
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from email.utils import parsedate_to_datetime
from typing import Any

import httpx
from pydantic import ValidationError

from jobs_back.models.enums import SalaryPeriod
from jobs_back.normalization.compensation import annualize_bounds
from jobs_back.providers.himalayas import _first, _timestamp
from jobs_back.providers.protocol import ProviderPageBatch
from jobs_back.providers.sanitize import strip_html
from jobs_back.schemas.discovery import JobResult, SearchFilters

logger = logging.getLogger(__name__)

API_BASE = "https://api.adzuna.com/v1/api/jobs"
DEFAULT_RESULTS_PER_PAGE = 20
DEFAULT_REQUEST_BUDGET = 50

ATTRIBUTION_URL = "https://www.adzuna.co.uk"
ATTRIBUTION_TEXT = (
    'This job listing is provided by Adzuna. Display "Jobs by Adzuna" with a '
    f"link to {ATTRIBUTION_URL} or the relevant local Adzuna domain."
)

COUNTRY_ALIASES: dict[str, str] = {
    "gb": "gb",
    "uk": "gb",
    "united kingdom": "gb",
    "great britain": "gb",
    "us": "us",
    "usa": "us",
    "united states": "us",
    "au": "au",
    "australia": "au",
    "ca": "ca",
    "canada": "ca",
    "de": "de",
    "germany": "de",
    "fr": "fr",
    "france": "fr",
    "in": "in",
    "india": "in",
    "nl": "nl",
    "netherlands": "nl",
    "nz": "nz",
    "new zealand": "nz",
    "pl": "pl",
    "poland": "pl",
    "sg": "sg",
    "singapore": "sg",
    "za": "za",
    "south africa": "za",
}

COUNTRY_CURRENCY: dict[str, str] = {
    "gb": "GBP",
    "us": "USD",
    "au": "AUD",
    "ca": "CAD",
    "de": "EUR",
    "fr": "EUR",
    "in": "INR",
    "nl": "EUR",
    "nz": "NZD",
    "pl": "PLN",
    "sg": "SGD",
    "za": "ZAR",
}

CONTRACT_TIME_MAP = {
    "full_time": "full_time",
    "part_time": "part_time",
}

CONTRACT_TYPE_MAP = {
    "permanent": "full_time",
    "contract": "contract",
    "temporary": "temporary",
    "internship": "internship",
}


def resolve_country_code(country: str | None, default: str) -> str:
    if not country or not country.strip():
        return default.lower()
    normalized = country.strip().lower()
    if len(normalized) == 2 and normalized.isalpha():
        return normalized
    return COUNTRY_ALIASES.get(normalized, normalized)


def _decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _employment_type(item: dict[str, Any]) -> str:
    contract_time = str(_first(item, "contract_time", default="")).lower()
    if contract_time in CONTRACT_TIME_MAP:
        return CONTRACT_TIME_MAP[contract_time]
    contract_type = str(_first(item, "contract_type", default="")).lower()
    return CONTRACT_TYPE_MAP.get(contract_type, "unspecified")


def normalize_job(
    item: dict[str, Any],
    *,
    queried_country: str,
) -> JobResult | None:
    job_id = _first(item, "id")
    title = _first(item, "title")
    if job_id is None or not title:
        logger.debug("Skipping malformed Adzuna row without id/title")
        return None
    job_id = str(job_id)
    redirect_url = _first(item, "redirect_url", "url")
    if redirect_url is None:
        logger.debug("Skipping Adzuna row %s without redirect_url", job_id)
        return None
    company = _first(item, "company")
    company_name = "Unknown company"
    if isinstance(company, dict):
        company_name = str(_first(company, "display_name", default=company_name))
    elif company:
        company_name = str(company)
    location = _first(item, "location")
    location_text = None
    if isinstance(location, dict):
        location_text = _first(location, "display_name")
    elif location:
        location_text = str(location)
    salary_min, salary_max = annualize_bounds(
        _decimal(_first(item, "salary_min")),
        _decimal(_first(item, "salary_max")),
        SalaryPeriod.YEARLY,
    )
    currency = _first(item, "salary_currency", "currency")
    if not currency:
        currency = COUNTRY_CURRENCY.get(queried_country.lower())
    raw_description = _first(item, "description")
    payload = dict(item)
    payload["attribution_text"] = ATTRIBUTION_TEXT
    payload["attribution_url"] = ATTRIBUTION_URL
    payload["queried_country"] = queried_country
    try:
        return JobResult(
            provider="adzuna",
            provider_job_id=job_id,
            title=str(title),
            company=company_name,
            description=strip_html(str(raw_description) if raw_description else None),
            location_text=location_text,
            employment_type=_employment_type(item),
            salary_min_annual=salary_min,
            salary_max_annual=salary_max,
            salary_currency=str(currency) if currency else None,
            job_url=str(redirect_url),
            apply_url=str(redirect_url),
            posted_at=_timestamp(_first(item, "created")),
            provider_payload=payload,
        )
    except ValidationError:
        logger.debug("Skipping unusable Adzuna row %s", job_id)
        return None


def _is_quota_rejection(response: httpx.Response) -> bool:
    if response.status_code not in {403, 429}:
        return False
    try:
        body = response.json()
    except ValueError:
        body = None
    if isinstance(body, dict):
        message = str(body.get("exception", body.get("error", ""))).lower()
        if "quota" in message or "limit" in message:
            return True
    text = response.text.lower()
    return "quota" in text or "limit exceeded" in text


class AdzunaProvider:
    key = "adzuna"

    def __init__(
        self,
        *,
        app_id: str,
        app_key: str,
        default_country: str = "gb",
        concurrency: int = 8,
        timeout: float = 20,
        max_retries: int = 3,
        request_budget: int = DEFAULT_REQUEST_BUDGET,
        results_per_page: int = DEFAULT_RESULTS_PER_PAGE,
    ) -> None:
        self._app_id = app_id
        self._app_key = app_key
        self._default_country = default_country.lower()
        self._client = httpx.AsyncClient(
            base_url=API_BASE,
            timeout=timeout,
            follow_redirects=True,
        )
        self._concurrency = concurrency
        self._max_retries = max_retries
        self._request_budget = max(1, request_budget)
        self._results_per_page = max(1, min(results_per_page, 50))
        self._requests_made = 0

    async def close(self) -> None:
        await self._client.aclose()

    def _country_for_filters(self, filters: SearchFilters) -> str:
        return resolve_country_code(filters.country, self._default_country)

    def _params(self, filters: SearchFilters) -> dict[str, str | int]:
        params: dict[str, str | int] = {
            "app_id": self._app_id,
            "app_key": self._app_key,
            "content-type": "application/json",
            "results_per_page": self._results_per_page,
        }
        if filters.query:
            params["what"] = filters.query
        if filters.location:
            params["where"] = filters.location
        if filters.minimum_salary is not None:
            params["salary_min"] = filters.minimum_salary
        if filters.posted_within_days is not None:
            params["max_days_old"] = filters.posted_within_days
        if "full_time" in filters.employment_types:
            params["full_time"] = 1
        if "part_time" in filters.employment_types:
            params["part_time"] = 1
        if "contract" in filters.employment_types:
            params["contract"] = 1
        return params

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

    async def _request_page(
        self,
        filters: SearchFilters,
        country: str,
        page: int,
    ) -> tuple[dict[str, Any] | None, str | None, bool]:
        """Return payload, warning, and whether quota was exhausted."""
        if self._requests_made >= self._request_budget:
            return None, "Adzuna request budget exhausted", True

        last_warning: str | None = None
        for attempt in range(self._max_retries):
            response: httpx.Response | None = None
            try:
                self._requests_made += 1
                response = await self._client.get(
                    f"/{country}/search/{page}",
                    params=self._params(filters),
                )
                if _is_quota_rejection(response):
                    return None, "Adzuna daily request quota exhausted", True
                if response.status_code == 429 or response.status_code >= 500:
                    last_warning = f"Adzuna page {page} returned {response.status_code}"
                    if attempt + 1 < self._max_retries:
                        await asyncio.sleep(self._retry_delay(response, attempt))
                        continue
                    return None, last_warning, False
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    return (
                        None,
                        f"Adzuna page {page} returned unexpected payload",
                        False,
                    )
                return payload, None, False
            except httpx.TimeoutException:
                last_warning = f"Adzuna page {page} timed out"
                if attempt + 1 < self._max_retries:
                    await asyncio.sleep(self._retry_delay(response, attempt))
                    continue
            except httpx.HTTPError as exc:
                last_warning = f"Adzuna page {page} request failed"
                logger.debug(
                    "Adzuna transport failure on page %s",
                    page,
                    exc_info=exc,
                )
                if attempt + 1 < self._max_retries:
                    await asyncio.sleep(self._retry_delay(response, attempt))
                    continue
        return None, last_warning, False

    def _normalize_page_items(
        self,
        raw_items: Any,
        *,
        queried_country: str,
    ) -> list[JobResult]:
        if not isinstance(raw_items, list):
            msg = "Adzuna payload did not contain a job list"
            raise ValueError(msg)
        normalized: list[JobResult] = []
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            job = normalize_job(item, queried_country=queried_country)
            if job is not None:
                normalized.append(job)
        return normalized

    async def pages(self, filters: SearchFilters) -> AsyncIterator[ProviderPageBatch]:
        country = self._country_for_filters(filters)
        payload, warning, quota_exhausted = await self._request_page(
            filters,
            country,
            1,
        )
        if payload is None:
            yield ProviderPageBatch(
                items=[],
                page=1,
                total_pages=1,
                warnings=(warning or "Adzuna page 1 failed",),
            )
            return

        try:
            raw_items = _first(payload, "results", default=[])
            total = int(_first(payload, "count", default=len(raw_items)))
            page_size = self._results_per_page
            total_pages = max(1, math.ceil(total / page_size))
            first_batch = ProviderPageBatch(
                items=self._normalize_page_items(
                    raw_items,
                    queried_country=country,
                ),
                page=1,
                total_pages=total_pages,
            )
        except (TypeError, ValueError):
            logger.debug("Adzuna page 1 could not be processed", exc_info=True)
            yield ProviderPageBatch(
                items=[],
                page=1,
                total_pages=1,
                warnings=("Adzuna page 1 failed",),
            )
            return
        yield first_batch

        if quota_exhausted or total_pages <= 1:
            if quota_exhausted and warning:
                yield ProviderPageBatch(
                    items=[],
                    page=1,
                    total_pages=total_pages,
                    warnings=(warning,),
                )
            return

        queue: asyncio.Queue[int | None] = asyncio.Queue()
        for page in range(2, total_pages + 1):
            queue.put_nowait(page)
        output: asyncio.Queue[ProviderPageBatch | None] = asyncio.Queue()
        worker_count = min(self._concurrency, total_pages - 1)
        for _ in range(worker_count):
            queue.put_nowait(None)

        async def worker() -> None:
            try:
                while True:
                    page = await queue.get()
                    if page is None:
                        return
                    try:
                        batch = await self._fetch_batch(
                            filters,
                            country,
                            page,
                            total_pages,
                        )
                    except Exception:
                        logger.debug(
                            "Adzuna page %s could not be processed",
                            page,
                            exc_info=True,
                        )
                        batch = ProviderPageBatch(
                            items=[],
                            page=page,
                            total_pages=total_pages,
                            warnings=(f"Adzuna page {page} failed",),
                        )
                    output.put_nowait(batch)
            finally:
                output.put_nowait(None)

        workers = [asyncio.create_task(worker()) for _ in range(worker_count)]
        try:
            finished = 0
            while finished < worker_count:
                result = await output.get()
                if result is None:
                    finished += 1
                    continue
                yield result
                if result.warnings and any(
                    "quota" in item.lower() or "budget" in item.lower()
                    for item in result.warnings
                ):
                    break
        finally:
            for task in workers:
                task.cancel()
            await asyncio.gather(*workers, return_exceptions=True)

    async def _fetch_batch(
        self,
        filters: SearchFilters,
        country: str,
        page: int,
        total_pages: int,
    ) -> ProviderPageBatch:
        if self._requests_made >= self._request_budget:
            return ProviderPageBatch(
                items=[],
                page=page,
                total_pages=total_pages,
                warnings=("Adzuna request budget exhausted",),
            )
        payload, warning, _quota_exhausted = await self._request_page(
            filters,
            country,
            page,
        )
        if payload is None:
            return ProviderPageBatch(
                items=[],
                page=page,
                total_pages=total_pages,
                warnings=(warning or f"Adzuna page {page} failed",),
            )
        raw_items = _first(payload, "results", default=[])
        return ProviderPageBatch(
            items=self._normalize_page_items(
                raw_items,
                queried_country=country,
            ),
            page=page,
            total_pages=total_pages,
        )
