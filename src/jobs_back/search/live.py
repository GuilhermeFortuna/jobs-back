from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy.orm import Session, sessionmaker

from jobs_back.providers.himalayas import HimalayasProvider
from jobs_back.providers.protocol import ProgressiveProvider
from jobs_back.schemas.discovery import JobResult, SearchFilters, SearchPage
from jobs_back.services.exceptions import (
    NotFoundError,
    SearchExpiredError,
    SearchJobNotFoundError,
)

if TYPE_CHECKING:
    from jobs_back.config import Settings

logger = logging.getLogger(__name__)

REUSE_WINDOW = timedelta(minutes=20)


def canonical_filters(filters: SearchFilters) -> SearchFilters:
    return SearchFilters(
        query=filters.query,
        country=filters.country,
        worldwide=filters.worldwide,
        seniority=sorted(filters.seniority),
        employment_types=sorted(filters.employment_types),
        minimum_salary=filters.minimum_salary,
        posted_within_days=filters.posted_within_days,
        sort=filters.sort,
    )


def filter_key(profile_id: UUID, filters: SearchFilters) -> tuple[UUID, str]:
    canonical = canonical_filters(filters)
    payload = json.dumps(canonical.model_dump(mode="json"), sort_keys=True)
    return profile_id, payload


@dataclass
class SearchState:
    id: UUID
    profile_id: UUID
    filters: SearchFilters
    status: str = "loading"
    progress: float = 0
    checked_count: int = 0
    expected_pages: int = 0
    completed_pages: int = 0
    items: list[JobResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


@dataclass(frozen=True)
class SearchStartResult:
    state: SearchState
    previous_search_id: UUID | None = None
    serving_search_id: UUID | None = None


class LiveSearchManager:
    """Process-local progressive indexes.

    PostgreSQL never receives search catalog rows.
    """

    def __init__(
        self,
        provider: ProgressiveProvider | None = None,
        *,
        settings: Settings | None = None,
    ) -> None:
        from jobs_back.config import get_settings

        self._settings = settings or get_settings()
        self.provider = provider or HimalayasProvider()
        self.states: dict[UUID, SearchState] = {}
        self.latest: dict[tuple[UUID, str], UUID] = {}
        self.refreshing: dict[tuple[UUID, str], UUID] = {}
        self.evicted: set[UUID] = set()
        self.tasks: set[asyncio.Task[None]] = set()
        self._background_tasks: set[asyncio.Task[None]] = set()
        self._closed = False

    def start_background_tasks(
        self, session_factory: sessionmaker[Session] | None = None
    ) -> None:
        self._track_task(asyncio.create_task(self._run_eviction_loop()))
        if session_factory is not None:
            self._track_task(asyncio.create_task(self.warm_defaults(session_factory)))

    def _track_task(self, task: asyncio.Task[None]) -> None:
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    def start(
        self, profile_id: UUID, filters: SearchFilters, *, force: bool = False
    ) -> SearchStartResult:
        key = filter_key(profile_id, filters)
        previous_search_id: UUID | None = None
        serving_search_id: UUID | None = None

        if not force:
            existing_id = self.latest.get(key)
            if existing_id:
                existing = self.states.get(existing_id)
                if (
                    existing
                    and existing.status != "failed"
                    and datetime.now(UTC) - existing.created_at < REUSE_WINDOW
                ):
                    return SearchStartResult(
                        state=existing,
                        serving_search_id=existing_id,
                    )

        if force:
            stale_id = self.latest.get(key)
            if stale_id:
                stale = self.states.get(stale_id)
                if stale and stale.status == "complete":
                    previous_search_id = stale_id
                    serving_search_id = stale_id

        state = SearchState(
            id=uuid4(),
            profile_id=profile_id,
            filters=canonical_filters(filters),
        )
        self.states[state.id] = state

        if force and previous_search_id is not None:
            self.refreshing[key] = state.id
        else:
            self.latest[key] = state.id
            serving_search_id = state.id

        self._schedule_populate(state, key)
        return SearchStartResult(
            state=state,
            previous_search_id=previous_search_id,
            serving_search_id=serving_search_id or state.id,
        )

    def _schedule_populate(self, state: SearchState, key: tuple[UUID, str]) -> None:
        coro = self._populate(state, key)
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(coro)
            return
        task = loop.create_task(coro)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    def serving_search_id(
        self, profile_id: UUID, filters: SearchFilters
    ) -> UUID | None:
        key = filter_key(profile_id, filters)
        refresh_id = self.refreshing.get(key)
        if refresh_id:
            stale_id = self.latest.get(key)
            if stale_id and self._should_promote(stale_id, refresh_id):
                self._promote_refresh(key)
            elif stale_id:
                return stale_id
        latest_id = self.latest.get(key)
        return latest_id

    def _should_promote(self, stale_id: UUID, refresh_id: UUID) -> bool:
        stale = self.states.get(stale_id)
        refresh = self.states.get(refresh_id)
        if refresh is None:
            return False
        if refresh.status == "complete":
            return True
        if stale is None:
            return refresh.checked_count > 0
        threshold = max(stale.checked_count, 25)
        return refresh.checked_count >= threshold

    def _promote_refresh(self, key: tuple[UUID, str]) -> None:
        refresh_id = self.refreshing.pop(key, None)
        if refresh_id is not None:
            self.latest[key] = refresh_id

    async def _populate(self, state: SearchState, key: tuple[UUID, str]) -> None:
        succeeded_pages = 0
        try:
            async for batch in self.provider.pages(state.filters):
                filtered = self._filter(batch.items, state.filters)
                async with state.lock:
                    if state.expected_pages == 0:
                        state.expected_pages = batch.total_pages
                    state.items.extend(filtered)
                    state.checked_count += len(batch.items)
                    state.completed_pages += 1
                    if state.expected_pages:
                        state.progress = min(
                            1.0, state.completed_pages / state.expected_pages
                        )
                    if batch.warnings:
                        state.warnings.extend(batch.warnings)
                    else:
                        succeeded_pages += 1

                if key in self.refreshing and self.refreshing[key] == state.id:
                    stale_id = self.latest.get(key)
                    if stale_id and self._should_promote(stale_id, state.id):
                        self._promote_refresh(key)

            async with state.lock:
                state.items = await asyncio.to_thread(
                    self._sort, state.items, state.filters
                )
                state.progress = 1
                if succeeded_pages:
                    state.status = "complete"
                else:
                    state.status = "failed"
                    if not state.warnings:
                        state.warnings.append("Search returned no usable results")

            if key in self.refreshing and self.refreshing[key] == state.id:
                self._promote_refresh(key)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            async with state.lock:
                if succeeded_pages or state.items:
                    state.items = await asyncio.to_thread(
                        self._sort, state.items, state.filters
                    )
                    state.progress = 1
                    state.status = "complete"
                    state.warnings.append(f"Search stopped early: {exc}")
                else:
                    state.status = "failed"
                    state.warnings.append(f"Search failed: {exc}")

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

    def page(
        self,
        search_id: UUID,
        page: int,
        page_size: int,
        profile_id: UUID | None = None,
    ) -> SearchPage | None:
        """Read one page. Callers outside the process must pass ``profile_id``."""
        if search_id in self.evicted:
            raise SearchExpiredError("Search not found or expired")
        state = self.states.get(search_id)
        if state is None:
            return None
        if profile_id is not None and state.profile_id != profile_id:
            raise NotFoundError("Search not found for this profile")
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
        if search_id in self.evicted:
            raise SearchExpiredError("Search not found or expired")
        state = self.states.get(search_id)
        if state is None:
            raise SearchExpiredError("Search not found or expired")
        if state.profile_id != profile_id:
            raise NotFoundError("Search not found for this profile")
        for item in state.items:
            if item.provider == provider and item.provider_job_id == provider_job_id:
                return item
        raise SearchJobNotFoundError("Job not found in search results")

    async def warm_defaults(self, session_factory: sessionmaker[Session]) -> None:
        from jobs_back.services.profile_library import list_profiles

        def load_profiles() -> list:
            session = session_factory()
            try:
                return list_profiles(session)
            finally:
                session.close()

        try:
            profiles = await asyncio.to_thread(load_profiles)
        except Exception:
            logger.warning("Startup search warming skipped: could not load profiles")
            return

        for profile in profiles:
            if self._closed:
                return
            try:
                filters = SearchFilters.model_validate(profile.preferences)
                self.start(profile.id, filters, force=False)
            except Exception:
                logger.warning(
                    "Startup search warming failed for profile %s",
                    profile.id,
                    exc_info=True,
                )

    async def _run_eviction_loop(self) -> None:
        interval = max(1, self._settings.search_eviction_interval_seconds)
        while not self._closed:
            try:
                await asyncio.sleep(interval)
                self.evict_expired()
            except asyncio.CancelledError:
                raise

    def evict_expired(self) -> None:
        now = datetime.now(UTC)
        ttl = timedelta(minutes=self._settings.search_state_ttl_minutes)
        candidates: list[tuple[datetime, UUID]] = []
        total_items = 0

        for search_id, state in self.states.items():
            total_items += len(state.items)
            candidates.append((state.created_at, search_id))

        candidates.sort(key=lambda item: item[0])
        to_evict: set[UUID] = set()

        for created_at, search_id in candidates:
            if now - created_at >= ttl:
                to_evict.add(search_id)

        while len(self.states) - len(to_evict) > self._settings.search_max_states:
            for _, search_id in candidates:
                if search_id not in to_evict:
                    to_evict.add(search_id)
                    break
            else:
                break

        remaining_items = total_items - sum(
            len(self.states[search_id].items)
            for search_id in to_evict
            if search_id in self.states
        )
        for _, search_id in candidates:
            if remaining_items <= self._settings.search_max_items:
                break
            if search_id in to_evict or search_id not in self.states:
                continue
            to_evict.add(search_id)
            remaining_items -= len(self.states[search_id].items)

        for search_id in to_evict:
            self._evict(search_id)

    def _evict(self, search_id: UUID) -> None:
        if search_id not in self.states:
            return
        self.evicted.add(search_id)
        self.states.pop(search_id, None)
        for key, latest_id in list(self.latest.items()):
            if latest_id == search_id:
                del self.latest[key]
        for key, refresh_id in list(self.refreshing.items()):
            if refresh_id == search_id:
                del self.refreshing[key]

    async def close(self) -> None:
        self._closed = True
        for task in list(self._background_tasks):
            task.cancel()
        await asyncio.gather(*self._background_tasks, return_exceptions=True)
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        await self.provider.close()
