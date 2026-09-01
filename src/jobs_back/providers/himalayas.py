from __future__ import annotations

import asyncio
import math
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from jobs_back.schemas.discovery import JobResult, SearchFilters

EMPLOYMENT_MAP = {
    "full time": "full_time",
    "part time": "part_time",
    "contractor": "contract",
    "temporary": "temporary",
    "intern": "internship",
    "volunteer": "other",
    "other": "other",
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
        if value is not None:
            return value
    return default


def _timestamp(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        # The live API currently returns Unix seconds despite older docs saying ms.
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
    try:
        return Decimal(str(value)) * PERIOD_FACTORS.get(
            (period or "annual").lower(), Decimal("1")
        )
    except (InvalidOperation, TypeError):
        return None


def normalize_job(item: dict[str, Any]) -> JobResult:
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
    job_id = str(_first(item, "id", "guid", "jobId", "slug"))
    url = _first(
        item,
        "applicationLink",
        "applyUrl",
        "url",
        default=f"https://himalayas.app/jobs/{job_id}",
    )
    return JobResult(
        provider_job_id=job_id,
        title=str(_first(item, "title", default="Untitled role")),
        company=str(_first(item, "companyName", "company", default="Unknown company")),
        description=_first(item, "description", "descriptionHtml"),
        location_text=", ".join(labels) if labels else "Remote worldwide",
        eligible_country_codes=sorted(set(countries)) or None,
        employment_type=EMPLOYMENT_MAP.get(employment, "unspecified"),
        seniority=seniority,
        salary_min_annual=_money(_first(item, "minSalary", "salaryMin"), period),
        salary_max_annual=_money(_first(item, "maxSalary", "salaryMax"), period),
        salary_currency=_first(item, "salaryCurrency", "currency"),
        job_url=str(url),
        apply_url=str(url),
        company_logo_url=_first(item, "companyLogo", "companyLogoUrl", "logo") or None,
        posted_at=_timestamp(_first(item, "pubDate", "publishedAt", "postedAt")),
        provider_payload=item,
    )


class HimalayasProvider:
    key = "himalayas"

    def __init__(self, *, concurrency: int = 12, timeout: float = 20) -> None:
        self._client = httpx.AsyncClient(
            base_url="https://himalayas.app", timeout=timeout, follow_redirects=True
        )
        self._concurrency = concurrency

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
            params.append(("employment_type", value))
        upstream_sort = {
            "newest": "recent",
            "salary": "salaryDesc",
            "relevance": "relevant",
        }[filters.sort]
        params.append(("sort", upstream_sort))
        return params

    async def _page(self, filters: SearchFilters, page: int) -> dict[str, Any]:
        response = await self._client.get(
            "/jobs/api/search", params=self._params(filters, page)
        )
        response.raise_for_status()
        return response.json()

    async def pages(
        self, filters: SearchFilters
    ) -> AsyncIterator[tuple[list[JobResult], int, int]]:
        first = await self._page(filters, 1)
        raw_items = _first(first, "jobs", "results", "items", default=[])
        total = int(_first(first, "totalCount", "total", default=len(raw_items)))
        page_size = max(1, int(_first(first, "limit", "pageSize", default=20)))
        total_pages = max(1, math.ceil(total / page_size))
        yield [normalize_job(item) for item in raw_items], 1, total_pages

        queue: asyncio.Queue[int] = asyncio.Queue()
        for page in range(2, total_pages + 1):
            queue.put_nowait(page)
        output: asyncio.Queue[tuple[int, list[JobResult]] | Exception] = asyncio.Queue()

        async def worker() -> None:
            while not queue.empty():
                try:
                    page = queue.get_nowait()
                except asyncio.QueueEmpty:
                    return
                try:
                    payload = await self._page(filters, page)
                    items = _first(payload, "jobs", "results", "items", default=[])
                    await output.put((page, [normalize_job(item) for item in items]))
                except (
                    Exception
                ) as exc:  # manager turns provider failures into warnings
                    await output.put(exc)
                finally:
                    queue.task_done()

        workers = [
            asyncio.create_task(worker())
            for _ in range(min(self._concurrency, total_pages - 1))
        ]
        try:
            for _ in range(2, total_pages + 1):
                result = await output.get()
                if isinstance(result, Exception):
                    raise result
                page, items = result
                yield items, page, total_pages
        finally:
            await asyncio.gather(*workers, return_exceptions=True)
