from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from email.utils import parsedate_to_datetime
from typing import Any

import httpx
from pydantic import ValidationError

from jobs_back.models.enums import SalaryPeriod
from jobs_back.normalization.compensation import annualize_amount, quantize_money
from jobs_back.providers.himalayas import _first, _timestamp
from jobs_back.providers.protocol import ProviderPageBatch
from jobs_back.providers.sanitize import strip_html
from jobs_back.schemas.discovery import JobResult, SearchFilters

logger = logging.getLogger(__name__)

# Observed practical cap when requesting Remotive listings in bulk.
RESULT_CAP = 50
API_BASE = "https://remotive.com/api"

ATTRIBUTION_URL = "https://remotive.com"
ATTRIBUTION_TEXT = (
    "This job listing is provided by Remotive. "
    f"Please link back to {ATTRIBUTION_URL} when displaying this listing."
)

EMPLOYMENT_MAP = {
    "full_time": "full_time",
    "full-time": "full_time",
    "part_time": "part_time",
    "part-time": "part_time",
    "contract": "contract",
    "freelance": "contract",
    "internship": "internship",
}

_CURRENCY_SYMBOLS: dict[str, str] = {
    "$": "USD",
    "€": "EUR",
    "£": "GBP",
}

_CURRENCY_CODES = frozenset({"USD", "EUR", "GBP", "CAD", "AUD", "CHF"})

_AMOUNT_PATTERN = re.compile(
    r"(?P<symbol>[$€£])?\s*"
    r"(?P<amount>\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)\s*"
    r"(?P<suffix>[kK])?",
    re.IGNORECASE,
)


def _parse_amount_token(match: re.Match[str]) -> Decimal | None:
    raw = match.group("amount").replace(",", "")
    try:
        value = Decimal(raw)
    except InvalidOperation:
        return None
    if match.group("suffix"):
        value *= 1000
    return quantize_money(value)


def _detect_currency(text: str, match: re.Match[str]) -> str | None:
    symbol = match.group("symbol")
    if symbol:
        return _CURRENCY_SYMBOLS.get(symbol)
    upper = text.upper()
    for code in _CURRENCY_CODES:
        if re.search(rf"\b{code}\b", upper):
            return code
    return None


def _detect_period(text: str) -> SalaryPeriod | None:
    lower = text.lower()
    if re.search(r"/\s*(year|yr|annum)|per\s+year|annually|annual", lower):
        return SalaryPeriod.YEARLY
    if re.search(r"/\s*month|per\s+month|monthly", lower):
        return SalaryPeriod.MONTHLY
    if re.search(r"/\s*hour|per\s+hour|hourly", lower):
        return SalaryPeriod.HOURLY
    if re.search(r"[kK]\b", text) and not re.search(
        r"/\s*(month|hour|week|day)", lower
    ):
        return SalaryPeriod.YEARLY
    return None


def parse_free_text_salary(
    text: str | None,
) -> tuple[Decimal | None, Decimal | None, str | None]:
    """Parse Remotive free-text salary conservatively.

    Annualizes only confident forms, never guesses currency, and never mirrors
    one figure into a range.
    """
    if text is None:
        return None, None, None
    cleaned = str(text).strip()
    if not cleaned:
        return None, None, None
    lower = cleaned.lower()
    if lower in {"competitive", "doe", "negotiable", "n/a", "na", "tbd"}:
        return None, None, None

    matches = list(_AMOUNT_PATTERN.finditer(cleaned))
    if not matches:
        return None, None, None

    period = _detect_period(cleaned)
    if period is None and len(matches) == 1 and not matches[0].group("suffix"):
        return None, None, None

    amounts: list[Decimal] = []
    currency: str | None = None
    for match in matches:
        amount = _parse_amount_token(match)
        if amount is None:
            return None, None, None
        detected = _detect_currency(cleaned, match)
        if detected is None:
            return None, None, None
        if currency is None:
            currency = detected
        elif currency != detected:
            return None, None, None
        amounts.append(amount)

    if period is None:
        period = SalaryPeriod.YEARLY

    annualized = [annualize_amount(amount, period) for amount in amounts]
    if any(value is None for value in annualized):
        return None, None, None

    if len(annualized) == 1:
        return annualized[0], None, currency
    if len(annualized) >= 2:
        low, high = sorted(annualized[:2])
        return low, high, currency
    return None, None, None


def normalize_job(item: dict[str, Any]) -> JobResult | None:
    job_id = _first(item, "id")
    title = _first(item, "title")
    if job_id is None or not title:
        logger.debug("Skipping malformed Remotive row without id/title")
        return None
    job_id = str(job_id)
    url = _first(item, "url")
    if url is None:
        url = f"https://remotive.com/remote-jobs/{job_id}"
    job_type = _first(item, "job_type")
    employment = "unspecified"
    if isinstance(job_type, str):
        employment = EMPLOYMENT_MAP.get(job_type.lower(), "unspecified")
    tags = item.get("tags") or []
    seniority = None
    if isinstance(tags, list) and tags:
        seniority = ", ".join(str(tag) for tag in tags[:5])
    salary_text = _first(item, "salary")
    salary_min, salary_max, salary_currency = parse_free_text_salary(
        str(salary_text) if salary_text is not None else None
    )
    raw_description = _first(item, "description")
    company = str(_first(item, "company_name", default="Unknown company"))
    payload = dict(item)
    payload["attribution_text"] = ATTRIBUTION_TEXT
    payload["attribution_url"] = ATTRIBUTION_URL
    location = _first(item, "candidate_required_location")
    try:
        return JobResult(
            provider="remotive",
            provider_job_id=job_id,
            title=str(title),
            company=company,
            description=strip_html(str(raw_description) if raw_description else None),
            location_text=str(location) if location else "Remote",
            employment_type=employment,
            seniority=seniority,
            salary_min_annual=salary_min,
            salary_max_annual=salary_max,
            salary_currency=salary_currency,
            job_url=str(url),
            apply_url=str(url),
            company_logo_url=_first(item, "company_logo") or None,
            posted_at=_timestamp(_first(item, "publication_date")),
            provider_payload=payload,
        )
    except ValidationError:
        logger.debug("Skipping unusable Remotive row %s", job_id)
        return None


class RemotiveProvider:
    key = "remotive"

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
        params: dict[str, str | int] = {"limit": self._result_cap}
        if filters.query:
            params["search"] = filters.query
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
                    last_warning = f"Remotive returned {response.status_code}"
                    if attempt + 1 < self._max_retries:
                        await asyncio.sleep(self._retry_delay(response, attempt))
                        continue
                    return None, last_warning
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    return None, "Remotive payload was not an object"
                return payload, None
            except httpx.TimeoutException:
                last_warning = "Remotive request timed out"
                if attempt + 1 < self._max_retries:
                    await asyncio.sleep(self._retry_delay(response, attempt))
                    continue
            except httpx.HTTPError:
                last_warning = "Remotive request failed"
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
                warnings=(warning or "Remotive request failed",),
            )
            return

        raw_jobs = payload.get("jobs", [])
        if not isinstance(raw_jobs, list):
            yield ProviderPageBatch(
                items=[],
                page=1,
                total_pages=1,
                warnings=("Remotive payload did not contain jobs",),
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
        total_reported = payload.get("total-job-count")
        if self._is_broad_search(filters) and (
            len(raw_jobs) >= self._result_cap
            or (isinstance(total_reported, int) and total_reported > len(raw_jobs))
        ):
            warnings.append(f"results truncated at {self._result_cap}")

        if not normalized:
            yield ProviderPageBatch(
                items=[],
                page=1,
                total_pages=1,
                warnings=tuple(warnings or ("Remotive returned no usable jobs",)),
            )
            return

        yield ProviderPageBatch(
            items=normalized,
            page=1,
            total_pages=1,
            warnings=tuple(warnings),
        )
