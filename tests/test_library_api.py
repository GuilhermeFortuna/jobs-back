"""PostgreSQL integration tests for personal job library API."""

from __future__ import annotations

import threading
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from jobs_back.api.searches import get_manager
from jobs_back.db import get_db
from jobs_back.main import create_app
from jobs_back.models.profile import Profile
from jobs_back.models.saved_job import SavedJob
from jobs_back.search.live import LiveSearchManager
from tests.conftest import seed_search
from tests.helpers.discovery import make_job_result


def _create_profile(client: TestClient, name: str) -> str:
    response = client.post("/profiles", json={"display_name": name})
    assert response.status_code == 201
    return response.json()["id"]


def test_two_profiles_isolated_library_rows(
    api_client_with_search: tuple[TestClient, object],
) -> None:
    client, manager = api_client_with_search
    profile_a = _create_profile(client, "Profile A")
    profile_b = _create_profile(client, "Profile B")
    job = make_job_result()
    search_a = seed_search(manager, uuid.UUID(profile_a), [job])
    search_b = seed_search(manager, uuid.UUID(profile_b), [job])

    save_a = client.post(
        f"/profiles/{profile_a}/jobs",
        json={
            "search_id": str(search_a),
            "provider": job.provider,
            "provider_job_id": job.provider_job_id,
            "state": "saved",
        },
    )
    save_b = client.post(
        f"/profiles/{profile_b}/jobs",
        json={
            "search_id": str(search_b),
            "provider": job.provider,
            "provider_job_id": job.provider_job_id,
            "state": "applied",
        },
    )
    assert save_a.status_code == 201
    assert save_b.status_code == 201
    assert save_a.json()["id"] != save_b.json()["id"]
    assert save_a.json()["state"] == "saved"
    assert save_b.json()["state"] == "applied"


def test_cross_profile_access_returns_404(
    api_client_with_search: tuple[TestClient, object],
) -> None:
    client, manager = api_client_with_search
    owner = _create_profile(client, "Owner")
    other = _create_profile(client, "Other")
    job = make_job_result()
    search_id = seed_search(manager, uuid.UUID(owner), [job])
    saved = client.post(
        f"/profiles/{owner}/jobs",
        json={
            "search_id": str(search_id),
            "provider": job.provider,
            "provider_job_id": job.provider_job_id,
        },
    )
    job_id = saved.json()["id"]

    assert client.get(f"/profiles/{other}/jobs/{job_id}").status_code == 404
    assert (
        client.patch(
            f"/profiles/{other}/jobs/{job_id}", json={"state": "applied"}
        ).status_code
        == 404
    )
    assert client.delete(f"/profiles/{other}/jobs/{job_id}").status_code == 404


def test_save_from_search_persists_snapshot(
    api_client_with_search: tuple[TestClient, object],
) -> None:
    client, manager = api_client_with_search
    profile_id = _create_profile(client, "Saver")
    job = make_job_result()
    search_id = seed_search(manager, uuid.UUID(profile_id), [job])

    response = client.post(
        f"/profiles/{profile_id}/jobs",
        json={
            "search_id": str(search_id),
            "provider": job.provider,
            "provider_job_id": job.provider_job_id,
            "state": "saved",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == job.title
    assert body["company"] == job.company
    assert "provider_payload" not in body


def test_expired_search_returns_410(
    api_client_with_search: tuple[TestClient, object],
) -> None:
    client, manager = api_client_with_search
    profile_id = _create_profile(client, "Expired")
    job = make_job_result()
    search_id = seed_search(manager, uuid.UUID(profile_id), [job])
    manager.states.pop(search_id)

    response = client.post(
        f"/profiles/{profile_id}/jobs",
        json={
            "search_id": str(search_id),
            "provider": job.provider,
            "provider_job_id": job.provider_job_id,
        },
    )
    assert response.status_code == 410


def test_repeat_save_is_idempotent(
    api_client_with_search: tuple[TestClient, object],
) -> None:
    client, manager = api_client_with_search
    profile_id = _create_profile(client, "Repeat")
    job = make_job_result()
    search_id = seed_search(manager, uuid.UUID(profile_id), [job])
    payload = {
        "search_id": str(search_id),
        "provider": job.provider,
        "provider_job_id": job.provider_job_id,
        "state": "saved",
    }

    first = client.post(f"/profiles/{profile_id}/jobs", json=payload)
    second = client.post(f"/profiles/{profile_id}/jobs", json=payload)
    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]

    listed = client.get(f"/profiles/{profile_id}/jobs")
    assert len(listed.json()) == 1


def test_concurrent_saves_create_one_row(
    committed_engine: object,
    search_manager: object,
) -> None:
    session_factory = sessionmaker(
        bind=committed_engine,
        autocommit=False,
        autoflush=False,
    )
    session = session_factory()
    profile = Profile(display_name=f"Concurrent-{uuid.uuid4().hex[:8]}")
    session.add(profile)
    session.commit()
    session.refresh(profile)

    job = make_job_result(provider_job_id=f"concurrent-{uuid.uuid4().hex[:8]}")
    search_id = seed_search(search_manager, profile.id, [job])
    payload = {
        "search_id": str(search_id),
        "provider": job.provider,
        "provider_job_id": job.provider_job_id,
        "state": "saved",
    }

    app = create_app()

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    def override_get_manager() -> LiveSearchManager:
        return search_manager  # type: ignore[return-value]

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_manager] = override_get_manager

    errors: list[Exception] = []

    def worker() -> None:
        try:
            with TestClient(app) as client:
                response = client.post(f"/profiles/{profile.id}/jobs", json=payload)
                assert response.status_code in {200, 201}
        except Exception as exc:  # pragma: no cover - surfaced below
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not errors
    session.expire_all()
    count = session.scalar(
        select(func.count())
        .select_from(SavedJob)
        .where(
            SavedJob.profile_id == profile.id,
            SavedJob.provider_job_id == job.provider_job_id,
        )
    )
    session.close()
    assert count == 1


def test_state_transitions_and_applied_at_semantics(
    api_client_with_search: tuple[TestClient, object],
) -> None:
    client, manager = api_client_with_search
    profile_id = _create_profile(client, "States")
    job = make_job_result()
    search_id = seed_search(manager, uuid.UUID(profile_id), [job])
    saved = client.post(
        f"/profiles/{profile_id}/jobs",
        json={
            "search_id": str(search_id),
            "provider": job.provider,
            "provider_job_id": job.provider_job_id,
            "state": "saved",
        },
    )
    job_id = saved.json()["id"]
    assert saved.json()["applied_at"] is None

    applied = client.patch(
        f"/profiles/{profile_id}/jobs/{job_id}", json={"state": "applied"}
    )
    assert applied.status_code == 200
    first_applied_at = applied.json()["applied_at"]
    assert first_applied_at is not None

    reapplied = client.patch(
        f"/profiles/{profile_id}/jobs/{job_id}", json={"state": "applied"}
    )
    assert reapplied.json()["applied_at"] == first_applied_at

    back_saved = client.patch(
        f"/profiles/{profile_id}/jobs/{job_id}", json={"state": "saved"}
    )
    assert back_saved.json()["applied_at"] is None


def test_delete_and_state_filtered_list(
    api_client_with_search: tuple[TestClient, object],
) -> None:
    client, manager = api_client_with_search
    profile_id = _create_profile(client, "DeleteMe")
    job = make_job_result(provider_job_id="delete-me")
    search_id = seed_search(manager, uuid.UUID(profile_id), [job])
    saved = client.post(
        f"/profiles/{profile_id}/jobs",
        json={
            "search_id": str(search_id),
            "provider": job.provider,
            "provider_job_id": job.provider_job_id,
            "state": "saved",
        },
    )
    job_id = saved.json()["id"]

    saved_list = client.get(f"/profiles/{profile_id}/jobs?state=saved")
    applied_list = client.get(f"/profiles/{profile_id}/jobs?state=applied")
    assert len(saved_list.json()) == 1
    assert applied_list.json() == []

    assert client.delete(f"/profiles/{profile_id}/jobs/{job_id}").status_code == 204
    assert client.get(f"/profiles/{profile_id}/jobs/{job_id}").status_code == 404


def test_snapshot_survives_search_cache_eviction(
    api_client_with_search: tuple[TestClient, object],
) -> None:
    client, manager = api_client_with_search
    profile_id = _create_profile(client, "Durable")
    job = make_job_result(provider_job_id="durable")
    search_id = seed_search(manager, uuid.UUID(profile_id), [job])
    saved = client.post(
        f"/profiles/{profile_id}/jobs",
        json={
            "search_id": str(search_id),
            "provider": job.provider,
            "provider_job_id": job.provider_job_id,
        },
    )
    job_id = saved.json()["id"]
    manager.states.pop(search_id)

    fetched = client.get(f"/profiles/{profile_id}/jobs/{job_id}")
    assert fetched.status_code == 200
    assert fetched.json()["title"] == job.title
    assert "provider_payload" not in fetched.json()


def test_list_ordering_uses_relevant_state_timestamp(
    api_client_with_search: tuple[TestClient, object],
) -> None:
    client, manager = api_client_with_search
    profile_id = _create_profile(client, "Ordering")
    older = make_job_result(provider_job_id="older")
    newer = make_job_result(provider_job_id="newer", title="Newer Role")
    search_id = seed_search(manager, uuid.UUID(profile_id), [older, newer])

    first = client.post(
        f"/profiles/{profile_id}/jobs",
        json={
            "search_id": str(search_id),
            "provider": older.provider,
            "provider_job_id": older.provider_job_id,
            "state": "saved",
        },
    )
    second = client.post(
        f"/profiles/{profile_id}/jobs",
        json={
            "search_id": str(search_id),
            "provider": newer.provider,
            "provider_job_id": newer.provider_job_id,
            "state": "saved",
        },
    )
    assert first.status_code == 201
    assert second.status_code == 201

    listed = client.get(f"/profiles/{profile_id}/jobs")
    ids = [item["provider_job_id"] for item in listed.json()]
    assert ids.index("newer") < ids.index("older")


def test_save_duplicate_from_second_provider_updates_existing_row(
    api_client_with_search: tuple[TestClient, object],
) -> None:
    client, manager = api_client_with_search
    profile_id = _create_profile(client, "DedupSave")
    primary = make_job_result(
        provider="himalayas",
        provider_job_id="h-1",
        company="Acme Corp, Inc.",
        title="Senior Python Developer",
    )
    alternate = make_job_result(
        provider="remoteok",
        provider_job_id="r-1",
        company="ACME CORP",
        title="Senior Python Developer",
        job_url="https://remoteok.com/jobs/1",
        apply_url="https://remoteok.com/jobs/1/apply",
    )
    search_id = seed_search(manager, uuid.UUID(profile_id), [primary, alternate])

    first = client.post(
        f"/profiles/{profile_id}/jobs",
        json={
            "search_id": str(search_id),
            "provider": primary.provider,
            "provider_job_id": primary.provider_job_id,
            "state": "saved",
        },
    )
    second = client.post(
        f"/profiles/{profile_id}/jobs",
        json={
            "search_id": str(search_id),
            "provider": alternate.provider,
            "provider_job_id": alternate.provider_job_id,
            "state": "saved",
        },
    )
    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    body = second.json()
    assert body["alternate_sources"]
    assert any(source["provider"] == "remoteok" for source in body["alternate_sources"])
    assert len(client.get(f"/profiles/{profile_id}/jobs").json()) == 1


def test_save_duplicate_preserves_applied_state_and_saved_at(
    api_client_with_search: tuple[TestClient, object],
) -> None:
    client, manager = api_client_with_search
    profile_id = _create_profile(client, "AppliedDedup")
    primary = make_job_result(
        provider="himalayas",
        provider_job_id="applied-1",
        company="Acme Corp",
        title="Backend Engineer",
    )
    alternate = make_job_result(
        provider="remoteok",
        provider_job_id="applied-2",
        company="Acme Corp, Inc.",
        title="Backend Engineer",
        job_url="https://remoteok.com/jobs/2",
    )
    search_id = seed_search(manager, uuid.UUID(profile_id), [primary, alternate])

    applied = client.post(
        f"/profiles/{profile_id}/jobs",
        json={
            "search_id": str(search_id),
            "provider": primary.provider,
            "provider_job_id": primary.provider_job_id,
            "state": "applied",
        },
    )
    saved_at = applied.json()["saved_at"]
    applied_at = applied.json()["applied_at"]

    duplicate = client.post(
        f"/profiles/{profile_id}/jobs",
        json={
            "search_id": str(search_id),
            "provider": alternate.provider,
            "provider_job_id": alternate.provider_job_id,
            "state": "saved",
        },
    )
    body = duplicate.json()
    assert body["state"] == "applied"
    assert body["saved_at"] == saved_at
    assert body["applied_at"] == applied_at


def test_library_and_search_responses_include_alternate_sources(
    api_client_with_search: tuple[TestClient, object],
) -> None:
    client, manager = api_client_with_search
    profile_id = _create_profile(client, "Schema")
    job = make_job_result()
    search_id = seed_search(manager, uuid.UUID(profile_id), [job])

    search_page = client.get(
        f"/searches/{search_id}?profile_id={profile_id}&page=1&page_size=10"
    )
    assert search_page.status_code == 200
    assert search_page.json()["items"][0]["alternate_sources"] == []

    saved = client.post(
        f"/profiles/{profile_id}/jobs",
        json={
            "search_id": str(search_id),
            "provider": job.provider,
            "provider_job_id": job.provider_job_id,
        },
    )
    assert saved.json()["alternate_sources"] == []


def test_duplicate_save_from_a_separate_search_keeps_every_source(
    api_client_with_search: tuple[TestClient, object],
) -> None:
    """Sources found in different searches must all survive (JE-008 AC 6)."""
    client, manager = api_client_with_search
    profile_id = _create_profile(client, "CrossSearchDedup")
    himalayas = make_job_result(
        provider="himalayas",
        provider_job_id="h-1",
        company="Acme Corp, Inc.",
        title="Senior Python Developer",
        job_url="https://himalayas.app/jobs/1",
        apply_url="https://himalayas.app/jobs/1/apply",
    )
    remoteok = make_job_result(
        provider="remoteok",
        provider_job_id="r-1",
        company="ACME CORP",
        title="Senior Python Developer",
        job_url="https://remoteok.com/jobs/1",
        apply_url="https://remoteok.com/jobs/1/apply",
    )
    first_search = seed_search(manager, uuid.UUID(profile_id), [himalayas])
    second_search = seed_search(manager, uuid.UUID(profile_id), [remoteok])

    client.post(
        f"/profiles/{profile_id}/jobs",
        json={
            "search_id": str(first_search),
            "provider": "himalayas",
            "provider_job_id": "h-1",
            "state": "saved",
        },
    )
    second = client.post(
        f"/profiles/{profile_id}/jobs",
        json={
            "search_id": str(second_search),
            "provider": "remoteok",
            "provider_job_id": "r-1",
            "state": "saved",
        },
    )

    assert second.status_code == 200
    body = second.json()
    reachable = {body["provider"]} | {
        source["provider"] for source in body["alternate_sources"]
    }
    assert reachable == {"himalayas", "remoteok"}
    urls = {body["job_url"]} | {
        source["job_url"] for source in body["alternate_sources"]
    }
    assert "https://himalayas.app/jobs/1" in urls
    assert len(client.get(f"/profiles/{profile_id}/jobs").json()) == 1
