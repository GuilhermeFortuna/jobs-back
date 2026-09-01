from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from jobs_back.providers.himalayas import HimalayasProvider
from jobs_back.schemas.discovery import JobResult, SearchFilters, SearchPage
from jobs_back.services.exceptions import (
    NotFoundError,
    SearchExpiredError,
    SearchJobNotFoundError,
)


@dataclass
class SearchState:
    id: UUID
    profile_id: UUID
    filters: SearchFilters
    status: str = "loading"
    progress: float = 0
    checked_count: int = 0
    items: list[JobResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class LiveSearchManager:
    """Process-local progressive indexes.

    PostgreSQL never receives search catalog rows.
    """

    def __init__(self, provider: HimalayasProvider | None = None) -> None:
        self.provider = provider or HimalayasProvider()
        self.states: dict[UUID, SearchState] = {}
        self.latest: dict[tuple[UUID, str], UUID] = {}
        self.tasks: set[asyncio.Task[None]] = set()

    @staticmethod
    def _key(profile_id: UUID, filters: SearchFilters) -> tuple[UUID, str]:
        return profile_id, filters.model_dump_json()

    def start(
        self, profile_id: UUID, filters: SearchFilters, *, force: bool = False
    ) -> SearchState:
        key = self._key(profile_id, filters)
        existing_id = self.latest.get(key)
        if existing_id and not force:
            existing = self.states.get(existing_id)
            if existing and datetime.now(UTC) - existing.created_at < timedelta(
                minutes=20
            ):
                return existing
        state = SearchState(id=uuid4(), profile_id=profile_id, filters=filters)
        self.states[state.id] = state
        self.latest[key] = state.id
        task = asyncio.create_task(self._populate(state))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return state

    async def _populate(self, state: SearchState) -> None:
        try:
            async for items, page, total_pages in self.provider.pages(state.filters):
                state.items.extend(self._filter(items, state.filters))
                state.checked_count += len(items)
                state.progress = page / total_pages
            state.items = await asyncio.to_thread(
                self._sort, state.items, state.filters
            )
            state.progress = 1
            state.status = "complete"
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            state.status = "failed"
            state.warnings.append(f"Himalayas search stopped early: {exc}")

    @staticmethod
    def _filter(items: list[JobResult], filters: SearchFilters) -> list[JobResult]:
        cutoff = (
            datetime.now(UTC) - timedelta(days=filters.posted_within_days)
            if filters.posted_within_days
            else None
        )
        filtered = []
        for item in items:
            if filters.minimum_salary is not None:
                ceiling = item.salary_max_annual or item.salary_min_annual
                if ceiling is None or ceiling < filters.minimum_salary:
                    continue
            if cutoff and (item.posted_at is None or item.posted_at < cutoff):
                continue
            filtered.append(item)
        return filtered

    @staticmethod
    def _sort(items: list[JobResult], filters: SearchFilters) -> list[JobResult]:
        if filters.sort == "newest":
            return sorted(
                items,
                key=lambda item: item.posted_at or datetime.min.replace(tzinfo=UTC),
                reverse=True,
            )
        if filters.sort == "salary":
            return sorted(
                items, key=lambda item: item.salary_max_annual or 0, reverse=True
            )
        return items

    def page(self, search_id: UUID, page: int, page_size: int) -> SearchPage | None:
        state = self.states.get(search_id)
        if state is None:
            return None
        start = (page - 1) * page_size
        complete = state.status in {"complete", "failed"}
        return SearchPage(
            search_id=state.id,
            status=state.status,
            progress=state.progress,
            checked_count=state.checked_count,
            items=state.items[start : start + page_size],
            page=page,
            page_size=page_size,
            total=len(state.items) if complete else None,
            is_complete=complete,
            warnings=state.warnings,
        )

    def resolve_job(
        self,
        search_id: UUID,
        profile_id: UUID,
        provider: str,
        provider_job_id: str,
    ) -> JobResult:
        state = self.states.get(search_id)
        if state is None:
            raise SearchExpiredError("Search not found or expired")
        if state.profile_id != profile_id:
            raise NotFoundError("Search not found for this profile")
        for item in state.items:
            if item.provider == provider and item.provider_job_id == provider_job_id:
                return item
        raise SearchJobNotFoundError("Job not found in search results")

    async def close(self) -> None:
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        await self.provider.close()
