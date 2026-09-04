from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any
from xml.etree import ElementTree

import httpx
from pydantic import ValidationError

from jobs_back.providers.himalayas import _timestamp
from jobs_back.providers.protocol import ProviderPageBatch
from jobs_back.providers.sanitize import strip_html
from jobs_back.schemas.discovery import JobResult, SearchFilters

logger = logging.getLogger(__name__)

FEED_URL = "https://weworkremotely.com/remote-jobs.rss"
# Observed practical upper bound for the public all-jobs feed.
FEED_ITEM_CAP = 100

ATTRIBUTION_URL = "https://weworkremotely.com"
ATTRIBUTION_TEXT = (
    "This job listing is provided by We Work Remotely. "
    f"Please link back to {ATTRIBUTION_URL} when displaying this listing."
)

EMPLOYMENT_MAP = {
    "full-time": "full_time",
    "full time": "full_time",
    "part-time": "part_time",
    "part time": "part_time",
    "contract": "contract",
    "contractor": "contract",
    "freelance": "contract",
    "internship": "internship",
}


def split_title_company(title: str | None) -> tuple[str | None, str | None]:
    if title is None:
        return None, None
    cleaned = title.strip()
    if not cleaned:
        return None, None
    if ":" not in cleaned:
        return None, cleaned
    company_part, role_part = cleaned.split(":", 1)
    company = company_part.strip() or None
    role = role_part.strip() or None
    return company, role


def _child_text(item: ElementTree.Element, tag: str) -> str | None:
    child = item.find(tag)
    if child is None or child.text is None:
        return None
    value = child.text.strip()
    return value or None


def _location_text(entry: dict[str, Any]) -> str | None:
    parts = [
        entry.get("region"),
        entry.get("country"),
        entry.get("state"),
    ]
    cleaned = [str(part).strip() for part in parts if part]
    if not cleaned:
        return None
    return ", ".join(cleaned)


def _parse_pub_date(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        parsed = parsedate_to_datetime(str(value))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed
    except (TypeError, ValueError):
        return _timestamp(value)


def parse_feed(xml: str) -> list[dict[str, Any]]:
    root = ElementTree.fromstring(xml)
    channel = root.find("channel")
    if channel is None:
        return []
    entries: list[dict[str, Any]] = []
    for item in channel.findall("item"):
        title = _child_text(item, "title")
        link = _child_text(item, "link")
        guid = _child_text(item, "guid")
        if not title or not (guid or link):
            continue
        description = _child_text(item, "description")
        content = _child_text(item, "{http://purl.org/rss/1.0/modules/content/}encoded")
        entries.append(
            {
                "title": title,
                "link": link,
                "guid": guid or link,
                "description": content or description,
                "pubDate": _child_text(item, "pubDate"),
                "region": _child_text(item, "region"),
                "country": _child_text(item, "country"),
                "state": _child_text(item, "state"),
                "skills": _child_text(item, "skills"),
                "category": _child_text(item, "category"),
                "type": _child_text(item, "type"),
            }
        )
    return entries


def normalize_job(entry: dict[str, Any]) -> JobResult | None:
    job_id = entry.get("guid") or entry.get("link")
    title_raw = entry.get("title")
    if not job_id or not title_raw:
        logger.debug("Skipping malformed We Work Remotely row without guid/title")
        return None
    company, title = split_title_company(str(title_raw))
    if not title:
        logger.debug("Skipping We Work Remotely row without title")
        return None
    link = entry.get("link") or job_id
    job_type = entry.get("type")
    employment = "unspecified"
    if isinstance(job_type, str):
        employment = EMPLOYMENT_MAP.get(job_type.lower(), "unspecified")
    skills = entry.get("skills")
    seniority = str(skills).strip() if skills else None
    raw_description = entry.get("description")
    payload = dict(entry)
    payload["attribution_text"] = ATTRIBUTION_TEXT
    payload["attribution_url"] = ATTRIBUTION_URL
    try:
        return JobResult(
            provider="weworkremotely",
            provider_job_id=str(job_id),
            title=title,
            company=company or "Unknown company",
            description=strip_html(str(raw_description) if raw_description else None),
            location_text=_location_text(entry),
            employment_type=employment,
            seniority=seniority,
            salary_min_annual=None,
            salary_max_annual=None,
            salary_currency=None,
            job_url=str(link),
            apply_url=str(link),
            company_logo_url=None,
            posted_at=_parse_pub_date(entry.get("pubDate")),
            provider_payload=payload,
        )
    except ValidationError:
        logger.debug("Skipping unusable We Work Remotely row %s", job_id)
        return None


class WeWorkRemotelyProvider:
    key = "weworkremotely"

    def __init__(
        self,
        *,
        timeout: float = 20,
        batch_size: int = 100,
        max_retries: int = 3,
        feed_item_cap: int = FEED_ITEM_CAP,
    ) -> None:
        self._client = httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": "JobScout/1.0"},
        )
        self._batch_size = max(1, batch_size)
        self._max_retries = max_retries
        self._feed_item_cap = max(1, feed_item_cap)

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

    async def _request(self) -> tuple[str | None, str | None]:
        last_warning: str | None = None
        for attempt in range(self._max_retries):
            response: httpx.Response | None = None
            try:
                response = await self._client.get(FEED_URL)
                if response.status_code == 429 or response.status_code >= 500:
                    last_warning = f"We Work Remotely returned {response.status_code}"
                    if attempt + 1 < self._max_retries:
                        await asyncio.sleep(self._retry_delay(response, attempt))
                        continue
                    return None, last_warning
                response.raise_for_status()
                return response.text, None
            except httpx.TimeoutException:
                last_warning = "We Work Remotely request timed out"
                if attempt + 1 < self._max_retries:
                    await asyncio.sleep(self._retry_delay(response, attempt))
                    continue
            except httpx.HTTPError:
                last_warning = "We Work Remotely request failed"
                if attempt + 1 < self._max_retries:
                    await asyncio.sleep(self._retry_delay(response, attempt))
                    continue
        return None, last_warning

    async def pages(self, filters: SearchFilters) -> AsyncIterator[ProviderPageBatch]:
        del filters
        xml, warning = await self._request()
        if xml is None:
            yield ProviderPageBatch(
                items=[],
                page=1,
                total_pages=1,
                warnings=(warning or "We Work Remotely request failed",),
            )
            return

        try:
            raw_entries = parse_feed(xml)
        except ElementTree.ParseError:
            yield ProviderPageBatch(
                items=[],
                page=1,
                total_pages=1,
                warnings=("We Work Remotely feed could not be parsed",),
            )
            return

        warnings: list[str] = []
        if warning:
            warnings.append(warning)
        if len(raw_entries) >= self._feed_item_cap:
            warnings.append(f"results truncated at {self._feed_item_cap}")

        normalized: list[JobResult] = []
        for entry in raw_entries[: self._feed_item_cap]:
            job = normalize_job(entry)
            if job is not None:
                normalized.append(job)

        if not normalized:
            yield ProviderPageBatch(
                items=[],
                page=1,
                total_pages=1,
                warnings=tuple(
                    warnings or ("We Work Remotely returned no usable jobs",)
                ),
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
                warnings=tuple(warnings) if index == 0 else (),
            )
