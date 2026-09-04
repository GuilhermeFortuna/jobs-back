from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy.orm import Session, sessionmaker

from jobs_back.normalization.dedup import derive_dedup_key
from jobs_back.providers.himalayas import HimalayasProvider
from jobs_back.providers.protocol import ProgressiveProvider
from jobs_back.schemas.discovery import (
    JobResult,
    ProviderSearchStatus,
    SearchFilters,
    SearchPage,
)
from jobs_back.search.consolidation import matches_source_identity, merge_results
from jobs_back.search.relevance import (
    job_matches_location,
    job_matches_query,
    normalize_query_tokens,
    score_job,
)
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
        location=filters.location,
        country=filters.country,
        worldwide=filters.worldwide,
        seniority=sorted(filters.seniority),
        employment_types=sorted(filters.employment_types),
        providers=sorted(filters.providers),
        minimum_salary=filters.minimum_salary,
        posted_within_days=filters.posted_within_days,
        sort=filters.sort,
    )


def filter_key(profile_id: UUID, filters: SearchFilters) -> tuple[UUID, str]:
    canonical = canonical_filters(filters)
    payload = json.dumps(canonical.model_dump(mode="json"), sort_keys=True)
    return profile_id, payload


@dataclass
class ProviderTracker:
    provider: str
    status: str = "loading"
    expected_pages: int = 0
    completed_pages: int = 0
    checked_count: int = 0
    progress: float = 0.0
    had_success: bool = False
    incomplete: bool = False


@dataclass
class SearchState:
    id: UUID
    profile_id: UUID
    filters: SearchFilters
    status: str = "loading"
    progress: float = 0
    checked_count: int = 0
    accepted_candidate_count: int = 0
    aggregate_exhausted: bool = False
    is_partial: bool = False
    provider_trackers: dict[str, ProviderTracker] = field(default_factory=dict)
    items: list[JobResult] = field(default_factory=list)
    dedup_index: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    profile_skills: list[tuple[str, str]] = field(default_factory=list)
    query_tokens: list[str] = field(default_factory=list)
    scored_at: datetime | None = None
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
        providers: Sequence[ProgressiveProvider] | None = None,
        *,
        settings: Settings | None = None,
        enabled_provider_count: int | None = None,
    ) -> None:
        from jobs_back.config import get_settings

        self._settings = settings or get_settings()
        if providers is not None:
            self.providers = list(providers)
        elif provider is not None:
            self.providers = [provider]
        else:
            self.providers = [HimalayasProvider()]
        provider_count = enabled_provider_count or len(self.providers)
        self._max_items = self._settings.effective_search_max_items(provider_count)
        self._max_candidates_per_search = (
            self._settings.search_max_candidates_per_search
        )
        self._max_states = self._settings.effective_search_max_states(provider_count)
        self.states: dict[UUID, SearchState] = {}
        self.latest: dict[tuple[UUID, str], UUID] = {}
        self.refreshing: dict[tuple[UUID, str], UUID] = {}
        self.evicted: set[UUID] = set()
        self.tasks: set[asyncio.Task[None]] = set()
        self._populate_tasks: dict[UUID, asyncio.Task[None]] = {}
        self._background_tasks: set[asyncio.Task[None]] = set()
        self._closed = False

    def start_background_tasks(self) -> None:
        self._track_task(asyncio.create_task(self._run_eviction_loop()))

    def _track_task(self, task: asyncio.Task[None]) -> None:
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    def start(
        self,
        profile_id: UUID,
        filters: SearchFilters,
        *,
        profile_skills: list[dict[str, str]] | None = None,
        force: bool = False,
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

        canonical = canonical_filters(filters)
        state = SearchState(
            id=uuid4(),
            profile_id=profile_id,
            filters=canonical,
            profile_skills=[
                (skill["label"], skill["token"]) for skill in (profile_skills or [])
            ],
            query_tokens=normalize_query_tokens(canonical.query),
            provider_trackers={
                provider.key: ProviderTracker(provider=provider.key)
                for provider in self._active_providers(filters)
            },
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
        self._populate_tasks[state.id] = task

        def _clear_task(done: asyncio.Task[None]) -> None:
            self.tasks.discard(done)
            self._populate_tasks.pop(state.id, None)

        task.add_done_callback(_clear_task)

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

    @staticmethod
    def _aggregate_progress(trackers: dict[str, ProviderTracker]) -> float:
        expected = sum(tracker.expected_pages for tracker in trackers.values())
        completed = sum(tracker.completed_pages for tracker in trackers.values())
        if expected <= 0:
            return 0.0
        return min(1.0, completed / expected)

    def _apply_batch(
        self,
        state: SearchState,
        tracker: ProviderTracker,
        batch_items: list[JobResult],
        batch: object,
        *,
        raw_count: int,
    ) -> None:
        from jobs_back.providers.protocol import ProviderPageBatch

        assert isinstance(batch, ProviderPageBatch)
        tracker.expected_pages = max(tracker.expected_pages, batch.total_pages)
        tracker.completed_pages += 1
        tracker.checked_count += raw_count
        if batch.warnings:
            if batch_items:
                tracker.had_success = True
            for warning in batch.warnings:
                state.warnings.append(f"{tracker.provider}: {warning}")
            tracker.incomplete = True
        else:
            tracker.had_success = True
        if tracker.expected_pages:
            tracker.progress = min(
                1.0,
                tracker.completed_pages / tracker.expected_pages,
            )
        state.checked_count = sum(
            t.checked_count for t in state.provider_trackers.values()
        )
        state.progress = max(
            state.progress,
            self._aggregate_progress(state.provider_trackers),
        )

    @classmethod
    def _enrich_result(cls, state: SearchState, item: JobResult) -> JobResult:
        now = state.scored_at or datetime.now(UTC)
        relevance_score, matched_skills = score_job(
            item,
            state.query_tokens,
            state.profile_skills,
            now=now,
        )
        return item.model_copy(
            update={
                "relevance_score": relevance_score,
                "matched_skills": matched_skills,
            }
        )

    @classmethod
    def _consolidate_items(
        cls,
        state: SearchState,
        items: list[JobResult],
    ) -> None:
        for item in items:
            enriched = cls._enrich_result(state, item)
            key = derive_dedup_key(enriched)
            if key in state.dedup_index:
                idx = state.dedup_index[key]
                merged = merge_results(state.items[idx], enriched)
                state.items[idx] = cls._enrich_result(state, merged)
            else:
                state.dedup_index[key] = len(state.items)
                state.items.append(enriched)

    async def _consume_provider(
        self,
        state: SearchState,
        search_key: tuple[UUID, str],
        provider: ProgressiveProvider,
    ) -> None:
        tracker = state.provider_trackers[provider.key]
        try:
            async for batch in provider.pages(state.filters):
                if state.aggregate_exhausted:
                    tracker.incomplete = True
                    break
                filtered = self._filter(batch.items, state)
                async with state.lock:
                    remaining = (
                        self._max_candidates_per_search - state.accepted_candidate_count
                    )
                    accepted = filtered[: max(0, remaining)]
                    state.accepted_candidate_count += len(accepted)
                    if len(accepted) < len(filtered):
                        tracker.incomplete = True
                        state.aggregate_exhausted = True
                        state.warnings.append(
                            "Search: candidate budget exhausted; results were truncated"
                        )
                    self._consolidate_items(state, accepted)
                    self._apply_batch(
                        state,
                        tracker,
                        accepted,
                        batch,
                        raw_count=len(batch.items),
                    )

                if state.aggregate_exhausted:
                    break

                refreshing = search_key in self.refreshing
                if refreshing and self.refreshing[search_key] == state.id:
                    stale_id = self.latest.get(search_key)
                    if stale_id and self._should_promote(stale_id, state.id):
                        self._promote_refresh(search_key)

            async with state.lock:
                tracker.progress = 1.0
                if tracker.had_success:
                    tracker.status = "complete"
                else:
                    tracker.status = "failed"
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            async with state.lock:
                tracker.status = "failed"
                tracker.progress = 1.0
                state.warnings.append(f"{provider.key}: provider unavailable ({exc})")
            logger.debug("Provider %s failed", provider.key, exc_info=exc)

    async def _complete_without_providers(self, state: SearchState) -> None:
        """No enabled provider matched the filter: an empty search, not a failure.

        A provider disabled by configuration can still be requested by a client,
        so this must not read as a failed search.
        """
        available = {provider.key for provider in self.providers}
        unavailable = sorted(set(state.filters.providers) - available)
        async with state.lock:
            state.items = []
            state.progress = 1.0
            state.status = "complete"
            state.is_partial = False
            if unavailable:
                state.warnings.append(
                    f"{', '.join(unavailable)}: provider is not enabled"
                )

    def _active_providers(self, filters: SearchFilters) -> list[ProgressiveProvider]:
        if not filters.providers:
            return list(self.providers)
        allowed = set(filters.providers)
        return [provider for provider in self.providers if provider.key in allowed]

    async def _populate(self, state: SearchState, key: tuple[UUID, str]) -> None:
        try:
            state.scored_at = datetime.now(UTC)
            active = self._active_providers(state.filters)
            tasks = [
                asyncio.create_task(self._consume_provider(state, key, provider))
                for provider in active
            ]
            await asyncio.gather(*tasks, return_exceptions=True)

            if not active:
                await self._complete_without_providers(state)
                if key in self.refreshing and self.refreshing[key] == state.id:
                    self._promote_refresh(key)
                return

            async with state.lock:
                state.items = await asyncio.to_thread(
                    self._sort, state.items, state.filters
                )
                state.progress = 1.0
                for tracker in state.provider_trackers.values():
                    tracker.progress = 1.0

                any_success = any(
                    tracker.had_success for tracker in state.provider_trackers.values()
                )
                if any_success:
                    state.status = "complete"
                    state.is_partial = any(
                        tracker.status == "failed" or tracker.incomplete
                        for tracker in state.provider_trackers.values()
                    )
                else:
                    state.status = "failed"
                    state.is_partial = False
                    if not state.warnings:
                        state.warnings.append("Search returned no usable results")

            if key in self.refreshing and self.refreshing[key] == state.id:
                if state.status == "failed":
                    self.refreshing.pop(key, None)
                else:
                    self._promote_refresh(key)
        except asyncio.CancelledError:
            raise

    @staticmethod
    def _filter(items: list[JobResult], state: SearchState) -> list[JobResult]:
        filters = state.filters
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
            if state.query_tokens and not job_matches_query(item, state.query_tokens):
                continue
            if filters.location and not job_matches_location(item, filters.location):
                continue
            filtered.append(item)
        return filtered

    @staticmethod
    def _tiebreak(item: JobResult) -> tuple[str, str]:
        return (item.provider, item.provider_job_id)

    @classmethod
    def _sort(cls, items: list[JobResult], filters: SearchFilters) -> list[JobResult]:
        if filters.sort == "newest":
            return sorted(
                items,
                key=lambda item: (
                    item.posted_at or datetime.min.replace(tzinfo=UTC),
                    cls._tiebreak(item),
                ),
                reverse=True,
            )
        if filters.sort == "salary":
            return sorted(
                items,
                key=lambda item: (item.salary_max_annual or 0, cls._tiebreak(item)),
                reverse=True,
            )
        return sorted(
            items,
            key=lambda item: (-item.relevance_score, cls._tiebreak(item)),
        )

    def _provider_statuses(self, state: SearchState) -> list[ProviderSearchStatus]:
        return [
            ProviderSearchStatus(
                provider=tracker.provider,
                status=tracker.status,  # type: ignore[arg-type]
                progress=tracker.progress,
                checked_count=tracker.checked_count,
            )
            for tracker in state.provider_trackers.values()
        ]

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
            status=state.status,  # type: ignore[arg-type]
            progress=state.progress,
            checked_count=state.checked_count,
            providers=self._provider_statuses(state),
            items=state.items[start : start + page_size],
            page=page,
            page_size=page_size,
            total=len(state.items) if complete else None,
            is_complete=complete,
            is_partial=state.is_partial,
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
            if matches_source_identity(item, provider, provider_job_id):
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
                self.start(
                    profile.id,
                    filters,
                    profile_skills=profile.skills,
                    force=False,
                )
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

    def discard_profile_searches(self, profile_id: UUID) -> None:
        search_ids = [
            search_id
            for search_id, state in self.states.items()
            if state.profile_id == profile_id
        ]
        for search_id in search_ids:
            task = self._populate_tasks.pop(search_id, None)
            if task is not None and not task.done():
                task.cancel()
            self._evict(search_id)

    def _is_budget_protected(self, search_id: UUID) -> bool:
        state = self.states.get(search_id)
        if state is None:
            return False
        if state.status == "loading":
            return True
        for key, refresh_id in self.refreshing.items():
            stale_id = self.latest.get(key)
            if stale_id == search_id and refresh_id != search_id:
                return True
        return False

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
                if not self._is_budget_protected(search_id):
                    to_evict.add(search_id)

        while len(self.states) - len(to_evict) > self._max_states:
            for _, search_id in candidates:
                if search_id in to_evict or self._is_budget_protected(search_id):
                    continue
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
            if remaining_items <= self._max_items:
                break
            if search_id in to_evict or search_id not in self.states:
                continue
            if self._is_budget_protected(search_id):
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
        for provider in self.providers:
            await provider.close()
