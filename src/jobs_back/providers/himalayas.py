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

from jobs_back.providers.protocol import ProviderPageBatch
from jobs_back.providers.sanitize import strip_html
from jobs_back.schemas.discovery import JobResult, SearchFilters

logger = logging.getLogger(__name__)


class _RequestBudget:
    """Atomic per-search transport budget shared by concurrent page workers."""

    def __init__(self, limit: int) -> None:
        self._remaining = limit
        self._lock = asyncio.Lock()

    async def consume(self) -> bool:
        async with self._lock:
            if self._remaining <= 0:
                return False
            self._remaining -= 1
            return True


EMPLOYMENT_MAP = {
    "full time": "full_time",
    "part time": "part_time",
    "contractor": "contract",
    "temporary": "temporary",
    "intern": "internship",
    "volunteer": "other",
    "other": "other",
}
UPSTREAM_EMPLOYMENT = {
    "full_time": "Full Time",
    "part_time": "Part Time",
    "contract": "Contractor",
    "temporary": "Temporary",
    "internship": "Intern",
    "other": "Other",
}
PERIOD_FACTORS = {
    "hourly": Decimal("2080"),
    "daily": Decimal("260"),
    "weekly": Decimal("52"),
    "fortnightly": Decimal("26"),
    "monthly": Decimal("12"),
    "annual": Decimal("1"),
    "yearly": Decimal("1"),
}


def _first(item: dict[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        value = item.get(name)
        if value is None or (isinstance(value, str) and not value.strip()):
            continue
        return value
    return default


def _timestamp(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, str) and value.strip().isdigit():
        value = float(value)
    if isinstance(value, (int, float)):
        if value > 10_000_000_000:
            value /= 1000
        return datetime.fromtimestamp(value, UTC)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except ValueError:
        return None


def _money(value: Any, period: str | None) -> Decimal | None:
    if value in (None, ""):
        return None
    factor = PERIOD_FACTORS.get((period or "annual").lower())
    if factor is None:
        logger.debug("Skipping Himalayas salary with unknown period %r", period)
        return None
    try:
        return Decimal(str(value)) * factor
    except (InvalidOperation, TypeError):
        return None


def normalize_job(item: dict[str, Any]) -> JobResult | None:
    period = str(_first(item, "salaryPeriod", "salary_period", default="annual"))
    restrictions = _first(
        item, "locationRestrictions", "location_restrictions", default=[]
    )
    countries: list[str] = []
    labels: list[str] = []
    for restriction in restrictions or []:
        if isinstance(restriction, str):
            labels.append(restriction)
        elif isinstance(restriction, dict):
            code = _first(restriction, "alpha2", "countryCode", "code")
            label = _first(restriction, "name", "country")
            if code:
                countries.append(str(code).upper())
            if label:
                labels.append(str(label))
    employment = str(
        _first(item, "employmentType", "employment_type", default="")
    ).lower()
    seniority = _first(item, "seniority", "seniorityLevel")
    if isinstance(seniority, list):
        seniority = ", ".join(str(value) for value in seniority)
    job_id = _first(item, "guid", "id", "jobId", "slug")
    title = _first(item, "title")
    if not job_id or not title:
        logger.debug("Skipping malformed Himalayas row without id/title")
        return None
    job_id = str(job_id)
    url = _first(item, "applicationLink", "applyUrl", "url")
    if url is None:
        # The stable identity is the guid, which is currently an application URL.
        url = (
            job_id
            if job_id.startswith(("http://", "https://"))
            else f"https://himalayas.app/jobs/{job_id}"
        )
    raw_description = _first(item, "description", "descriptionHtml")
    try:
        return JobResult(
            provider_job_id=job_id,
            title=str(title),
            company=str(
                _first(item, "companyName", "company", default="Unknown company")
            ),
            description=strip_html(str(raw_description) if raw_description else None),
            location_text=", ".join(labels) if labels else "Remote worldwide",
            eligible_country_codes=sorted(set(countries)) or None,
            employment_type=EMPLOYMENT_MAP.get(employment, "unspecified"),
            seniority=str(seniority) if seniority is not None else None,
            salary_min_annual=_money(_first(item, "minSalary", "salaryMin"), period),
            salary_max_annual=_money(_first(item, "maxSalary", "salaryMax"), period),
            salary_currency=_first(item, "salaryCurrency", "currency"),
            job_url=str(url),
            apply_url=str(url),
            company_logo_url=_first(item, "companyLogo", "companyLogoUrl", "logo")
            or None,
            posted_at=_timestamp(_first(item, "pubDate", "publishedAt", "postedAt")),
            provider_payload=item,
        )
    except ValidationError:
        logger.debug("Skipping unusable Himalayas row %s", job_id)
        return None


class HimalayasProvider:
    key = "himalayas"

    def __init__(
        self,
        *,
        concurrency: int = 12,
        timeout: float = 20,
        max_retries: int = 3,
        request_budget: int = 10,
        result_cap: int = 200,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url="https://himalayas.app", timeout=timeout, follow_redirects=True
        )
        self._concurrency = concurrency
        self._max_retries = max_retries
        self._request_budget = max(1, request_budget)
        self._result_cap = max(1, result_cap)

    async def close(self) -> None:
        await self._client.aclose()

    def _params(self, filters: SearchFilters, page: int) -> list[tuple[str, str | int]]:
        params: list[tuple[str, str | int]] = [("page", page)]
        if filters.query:
            params.append(("q", filters.query))
        if filters.country:
            params.append(("country", filters.country))
        if filters.worldwide is True:
            params.append(("worldwide", "true"))
        elif filters.worldwide is False:
            params.append(("exclude_worldwide", "true"))
        for value in filters.seniority:
            params.append(("seniority", value))
        for value in filters.employment_types:
            upstream = UPSTREAM_EMPLOYMENT.get(value, value)
            params.append(("employment_type", upstream))
        upstream_sort = {
            "newest": "recent",
            "salary": "salaryDesc",
            "relevance": "relevant",
        }[filters.sort]
        params.append(("sort", upstream_sort))
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
        self, filters: SearchFilters, page: int, budget: _RequestBudget
    ) -> tuple[dict[str, Any] | None, str | None]:
        last_warning: str | None = None
        for attempt in range(self._max_retries):
            if not await budget.consume():
                return None, "Himalayas request budget exhausted"
            response: httpx.Response | None = None
            try:
                response = await self._client.get(
                    "/jobs/api/search", params=self._params(filters, page)
                )
                if response.status_code == 429 or response.status_code >= 500:
                    last_warning = (
                        f"Himalayas page {page} returned {response.status_code}"
                    )
                    if attempt + 1 < self._max_retries:
                        await asyncio.sleep(self._retry_delay(response, attempt))
                        continue
                    return None, last_warning
                response.raise_for_status()
                return response.json(), None
            except httpx.TimeoutException:
                last_warning = f"Himalayas page {page} timed out"
                if attempt + 1 < self._max_retries:
                    await asyncio.sleep(self._retry_delay(response, attempt))
                    continue
            except httpx.HTTPError as exc:
                last_warning = f"Himalayas page {page} request failed"
                logger.debug(
                    "Himalayas transport failure on page %s",
                    page,
                    exc_info=exc,
                )
                if attempt + 1 < self._max_retries:
                    await asyncio.sleep(self._retry_delay(response, attempt))
                    continue
        return None, last_warning

    def _normalize_page_items(self, raw_items: Any) -> list[JobResult]:
        if not isinstance(raw_items, list):
            msg = "Himalayas payload did not contain a job list"
            raise ValueError(msg)
        normalized: list[JobResult] = []
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            job = normalize_job(item)
            if job is not None:
                normalized.append(job)
        return normalized

    async def pages(self, filters: SearchFilters) -> AsyncIterator[ProviderPageBatch]:
        budget = _RequestBudget(self._request_budget)
        accepted = 0

        def cap(items: list[JobResult]) -> tuple[list[JobResult], tuple[str, ...]]:
            nonlocal accepted
            remaining = self._result_cap - accepted
            capped = items[: max(0, remaining)]
            accepted += len(capped)
            return capped, (
                (f"results truncated at {self._result_cap}",)
                if len(capped) < len(items)
                else ()
            )

        payload, warning = await self._request_page(filters, 1, budget)
        if payload is None:
            yield ProviderPageBatch(
                items=[],
                page=1,
                total_pages=1,
                warnings=(warning or "Himalayas page 1 failed",),
            )
            return

        try:
            raw_items = _first(payload, "jobs", "results", "items", default=[])
            total = int(_first(payload, "totalCount", "total", default=len(raw_items)))
            page_size = max(1, int(_first(payload, "limit", "pageSize", default=20)))
            total_pages = max(1, math.ceil(total / page_size))
            items, warnings = cap(self._normalize_page_items(raw_items))
            trunc = f"results truncated at {self._result_cap}"
            if (
                accepted >= self._result_cap
                and total_pages > 1
                and trunc not in warnings
            ):
                warnings = (*warnings, trunc)
            first_batch = ProviderPageBatch(
                items=items,
                page=1,
                total_pages=total_pages,
                warnings=warnings,
            )
        except (TypeError, ValueError):
            logger.debug("Himalayas page 1 could not be processed", exc_info=True)
            yield ProviderPageBatch(
                items=[],
                page=1,
                total_pages=1,
                warnings=("Himalayas page 1 failed",),
            )
            return
        yield first_batch

        if total_pages <= 1 or accepted >= self._result_cap:
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
                            filters, page, total_pages, budget
                        )
                    except Exception:
                        logger.debug(
                            "Himalayas page %s could not be processed",
                            page,
                            exc_info=True,
                        )
                        batch = ProviderPageBatch(
                            items=[],
                            page=page,
                            total_pages=total_pages,
                            warnings=(f"Himalayas page {page} failed",),
                        )
                    output.put_nowait(batch)
            finally:
                # A worker that stops for any reason still releases the consumer.
                output.put_nowait(None)

        workers = [asyncio.create_task(worker()) for _ in range(worker_count)]
        try:
            finished = 0
            while finished < worker_count:
                result = await output.get()
                if result is None:
                    finished += 1
                    continue
                items, warnings = cap(result.items)
                combined = result.warnings + warnings
                trunc = f"results truncated at {self._result_cap}"
                if (
                    accepted >= self._result_cap
                    and result.page < total_pages
                    and trunc not in combined
                ):
                    combined = (*combined, trunc)
                yield ProviderPageBatch(
                    items=items,
                    page=result.page,
                    total_pages=result.total_pages,
                    warnings=combined,
                )
                if accepted >= self._result_cap:
                    break
        finally:
            for task in workers:
                task.cancel()
            await asyncio.gather(*workers, return_exceptions=True)

    async def _fetch_batch(
        self,
        filters: SearchFilters,
        page: int,
        total_pages: int,
        budget: _RequestBudget,
    ) -> ProviderPageBatch:
        payload, warning = await self._request_page(filters, page, budget)
        if payload is None:
            return ProviderPageBatch(
                items=[],
                page=page,
                total_pages=total_pages,
                warnings=(warning or f"Himalayas page {page} failed",),
            )
        raw_items = _first(payload, "jobs", "results", "items", default=[])
        return ProviderPageBatch(
            items=self._normalize_page_items(raw_items),
            page=page,
            total_pages=total_pages,
        )
