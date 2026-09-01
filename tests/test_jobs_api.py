"""PostgreSQL integration tests for the job search API."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from jobs_back.models.enums import (
    EmploymentType,
    JobStatus,
    RemoteType,
    SalaryPeriod,
)
from jobs_back.search.constants import JOB_SEARCH_VECTOR_SQL
from tests.helpers.jobs import make_job

T0 = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
T1 = datetime(2026, 1, 2, 12, 0, tzinfo=UTC)
T2 = datetime(2026, 1, 3, 12, 0, tzinfo=UTC)
T3 = datetime(2026, 1, 4, 12, 0, tzinfo=UTC)


@pytest.fixture
def seed_jobs(db_session: Session) -> dict[str, uuid.UUID]:
    """Seed a diverse job set and return stable IDs by key."""
    jobs = [
        make_job(
            provider_job_id="active-remote-us",
            title="Senior Python Developer",
            company="Acme Corp",
            description="Build distributed systems with Python",
            remote_type=RemoteType.REMOTE.value,
            employment_type=EmploymentType.FULL_TIME.value,
            location_text="Remote - US",
            city="Austin",
            region="TX",
            country_code="US",
            eligible_country_codes=["US"],
            salary_min=Decimal("120000"),
            salary_max=Decimal("150000"),
            salary_currency="USD",
            salary_period=SalaryPeriod.YEARLY.value,
            salary_min_annual=Decimal("120000"),
            salary_max_annual=Decimal("150000"),
            posted_at=T2,
            discovered_at=T1,
        ),
        make_job(
            provider_job_id="active-hybrid-ca",
            title="Backend Engineer",
            company="Maple Tech",
            description="Go and PostgreSQL services",
            provider="maple",
            remote_type=RemoteType.HYBRID.value,
            employment_type=EmploymentType.CONTRACT.value,
            city="Toronto",
            region="ON",
            country_code="CA",
            eligible_country_codes=["CA", "US"],
            salary_min=Decimal("90000"),
            salary_max=Decimal("110000"),
            salary_currency="CAD",
            salary_period=SalaryPeriod.YEARLY.value,
            salary_min_annual=Decimal("90000"),
            salary_max_annual=Decimal("110000"),
            posted_at=T3,
            discovered_at=T2,
        ),
        make_job(
            provider_job_id="active-onsite-uk",
            title="Platform Engineer",
            company="London Labs",
            description="Kubernetes platform work",
            provider="london",
            remote_type=RemoteType.ON_SITE.value,
            employment_type=EmploymentType.FULL_TIME.value,
            city="London",
            country_code="GB",
            eligible_country_codes=[],
            salary_min=Decimal("80000"),
            salary_currency="GBP",
            salary_period=SalaryPeriod.YEARLY.value,
            salary_min_annual=Decimal("80000"),
            salary_max_annual=Decimal("80000"),
            posted_at=T1,
            discovered_at=T0,
        ),
        make_job(
            provider_job_id="active-no-salary",
            title="Junior Analyst",
            company="Data Co",
            description="Entry level analytics",
            remote_type=RemoteType.UNSPECIFIED.value,
            employment_type=EmploymentType.INTERNSHIP.value,
            eligible_country_codes=None,
            posted_at=None,
            discovered_at=T0,
        ),
        make_job(
            provider_job_id="active-one-sided-salary",
            title="DevOps Engineer",
            company="Cloud Inc",
            description="AWS and Terraform",
            remote_type=RemoteType.REMOTE.value,
            eligible_country_codes=["US"],
            salary_max=Decimal("130000"),
            salary_currency="USD",
            salary_period=SalaryPeriod.YEARLY.value,
            salary_max_annual=Decimal("130000"),
            posted_at=T2,
            discovered_at=T1,
        ),
        make_job(
            provider_job_id="inactive-job",
            title="Retired Role",
            company="Old Co",
            description="No longer hiring",
            status=JobStatus.INACTIVE.value,
            inactive_at=T3,
            posted_at=T0,
            discovered_at=T0,
        ),
        make_job(
            provider_job_id="tied-timestamp-a",
            title="Tied Job A",
            company="Tie Co",
            description="Same timestamp",
            posted_at=T2,
            discovered_at=T1,
        ),
        make_job(
            provider_job_id="tied-timestamp-b",
            title="Tied Job B",
            company="Tie Co",
            description="Same timestamp",
            posted_at=T2,
            discovered_at=T1,
        ),
    ]
    db_session.add_all(jobs)
    db_session.flush()
    return {job.provider_job_id: job.id for job in jobs}


def test_list_returns_only_active_jobs(
    api_client: TestClient,
    seed_jobs: dict[str, uuid.UUID],
) -> None:
    response = api_client.get("/jobs")
    assert response.status_code == 200
    body = response.json()
    ids = {item["id"] for item in body["items"]}
    assert str(seed_jobs["inactive-job"]) not in ids
    assert body["total"] == 7


def test_list_pagination_first_partial_last_past_end(
    api_client: TestClient,
    seed_jobs: dict[str, uuid.UUID],
) -> None:
    first = api_client.get("/jobs", params={"page": 1, "page_size": 3})
    assert first.status_code == 200
    first_body = first.json()
    assert len(first_body["items"]) == 3
    assert first_body["page"] == 1
    assert first_body["page_size"] == 3
    assert first_body["total"] == 7
    assert first_body["total_pages"] == 3

    last = api_client.get("/jobs", params={"page": 3, "page_size": 3})
    last_body = last.json()
    assert len(last_body["items"]) == 1

    past_end = api_client.get("/jobs", params={"page": 99, "page_size": 3})
    past_body = past_end.json()
    assert past_body["items"] == []
    assert past_body["total"] == 7
    assert past_body["total_pages"] == 3


def test_list_empty_result_pagination(
    api_client: TestClient,
    seed_jobs: dict[str, uuid.UUID],
) -> None:
    response = api_client.get("/jobs", params={"provider": "nonexistent"})
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["total"] == 0
    assert body["total_pages"] == 0


def test_keyword_search_title_company_description(
    api_client: TestClient,
    seed_jobs: dict[str, uuid.UUID],
) -> None:
    title = api_client.get("/jobs", params={"q": "Python"})
    assert title.status_code == 200
    assert len(title.json()["items"]) == 1
    assert title.json()["items"][0]["title"] == "Senior Python Developer"

    company = api_client.get("/jobs", params={"q": "Maple"})
    assert company.status_code == 200
    assert len(company.json()["items"]) == 1

    description = api_client.get("/jobs", params={"q": "Terraform"})
    assert description.status_code == 200
    assert len(description.json()["items"]) == 1


def test_keyword_search_malformed_punctuation_does_not_error(
    api_client: TestClient,
    seed_jobs: dict[str, uuid.UUID],
) -> None:
    response = api_client.get("/jobs", params={"q": 'python & (dev | "foo"'})
    assert response.status_code == 200


def test_keyword_search_empty_query_has_no_filter_effect(
    api_client: TestClient,
    seed_jobs: dict[str, uuid.UUID],
) -> None:
    response = api_client.get("/jobs", params={"q": ""})
    assert response.status_code == 200
    assert response.json()["total"] == 7


def test_location_filter_case_insensitive(
    api_client: TestClient,
    seed_jobs: dict[str, uuid.UUID],
) -> None:
    response = api_client.get("/jobs", params={"location": "austin"})
    assert response.status_code == 200
    assert len(response.json()["items"]) == 1
    assert response.json()["items"][0]["city"] == "Austin"

    country = api_client.get("/jobs", params={"location": "gb"})
    assert country.status_code == 200
    assert len(country.json()["items"]) == 1


def test_remote_type_or_within_and_and_across_filters(
    api_client: TestClient,
    seed_jobs: dict[str, uuid.UUID],
) -> None:
    or_response = api_client.get(
        "/jobs",
        params=[("remote_type", "remote"), ("remote_type", "hybrid")],
    )
    assert or_response.status_code == 200
    assert or_response.json()["total"] == 5

    and_response = api_client.get(
        "/jobs",
        params=[("remote_type", "remote"), ("provider", "example")],
    )
    assert and_response.status_code == 200
    assert and_response.json()["total"] == 4


def test_employment_type_and_provider_filters(
    api_client: TestClient,
    seed_jobs: dict[str, uuid.UUID],
) -> None:
    employment = api_client.get("/jobs", params={"employment_type": "contract"})
    assert employment.status_code == 200
    assert employment.json()["total"] == 1

    provider = api_client.get("/jobs", params={"provider": "maple"})
    assert provider.status_code == 200
    assert provider.json()["total"] == 1


def test_eligible_country_matches_explicit_and_worldwide_excludes_unknown(
    api_client: TestClient,
    seed_jobs: dict[str, uuid.UUID],
) -> None:
    us = api_client.get("/jobs", params={"eligible_country": "US"})
    assert us.status_code == 200
    assert us.json()["total"] == 4

    unknown_excluded = api_client.get(
        "/jobs",
        params={"eligible_country": "US", "provider": "example", "q": "Analyst"},
    )
    assert unknown_excluded.status_code == 200
    assert unknown_excluded.json()["total"] == 0


def test_posted_after_excludes_missing_posted_at(
    api_client: TestClient,
    seed_jobs: dict[str, uuid.UUID],
) -> None:
    response = api_client.get(
        "/jobs",
        params={"posted_after": T2.isoformat().replace("+00:00", "Z")},
    )
    assert response.status_code == 200
    titles = {item["title"] for item in response.json()["items"]}
    assert "Junior Analyst" not in titles
    assert "Backend Engineer" in titles


def test_salary_overlap_and_currency_isolation(
    api_client: TestClient,
    seed_jobs: dict[str, uuid.UUID],
) -> None:
    overlap = api_client.get(
        "/jobs",
        params={
            "salary_min": "125000",
            "salary_max": "135000",
            "salary_currency": "USD",
        },
    )
    assert overlap.status_code == 200
    assert overlap.json()["total"] == 2

    cad_only = api_client.get(
        "/jobs",
        params={
            "salary_min": "85000",
            "salary_max": "95000",
            "salary_currency": "CAD",
        },
    )
    assert cad_only.status_code == 200
    assert cad_only.json()["total"] == 1

    no_annual = api_client.get(
        "/jobs",
        params={
            "salary_min": "1",
            "salary_currency": "USD",
        },
    )
    assert no_annual.status_code == 200
    titles = {item["title"] for item in no_annual.json()["items"]}
    assert "Junior Analyst" not in titles


def test_salary_sort_asc_and_desc_null_last_excludes_other_currency(
    api_client: TestClient,
    seed_jobs: dict[str, uuid.UUID],
) -> None:
    asc = api_client.get(
        "/jobs",
        params={"sort": "salary_asc", "salary_currency": "USD"},
    )
    assert asc.status_code == 200
    asc_items = asc.json()["items"]
    usd_titles = [
        item["title"] for item in asc_items if item["salary_currency"] == "USD"
    ]
    assert usd_titles[0] == "Senior Python Developer"
    null_annual_titles = {
        item["title"]
        for item in asc_items
        if item["salary_min_annual"] is None and item["salary_max_annual"] is None
    }
    assert "Junior Analyst" in null_annual_titles
    assert all(item["salary_currency"] in (None, "USD") for item in asc_items)
    assert all(item["salary_currency"] != "CAD" for item in asc_items)

    desc = api_client.get(
        "/jobs",
        params={"sort": "salary_desc", "salary_currency": "USD"},
    )
    assert desc.status_code == 200
    desc_items = desc.json()["items"]
    assert desc_items[0]["title"] == "Senior Python Developer"


def test_newest_sort_uses_discovered_at_fallback_and_id_tiebreak(
    api_client: TestClient,
    seed_jobs: dict[str, uuid.UUID],
) -> None:
    response = api_client.get("/jobs", params={"sort": "newest"})
    assert response.status_code == 200
    items = response.json()["items"]
    assert items[0]["title"] == "Backend Engineer"

    tied = [
        item
        for item in items
        if item["provider_job_id"] in ("tied-timestamp-a", "tied-timestamp-b")
    ]
    assert len(tied) == 2
    assert tied[0]["id"] > tied[1]["id"]


def test_combined_filters(
    api_client: TestClient,
    seed_jobs: dict[str, uuid.UUID],
) -> None:
    response = api_client.get(
        "/jobs",
        params={
            "remote_type": "remote",
            "eligible_country": "US",
            "salary_min": "100000",
            "salary_currency": "USD",
        },
    )
    assert response.status_code == 200
    assert response.json()["total"] == 2


def test_detail_returns_active_and_inactive(
    api_client: TestClient,
    seed_jobs: dict[str, uuid.UUID],
) -> None:
    active = api_client.get(f"/jobs/{seed_jobs['active-remote-us']}")
    assert active.status_code == 200
    assert active.json()["status"] == "active"
    assert "description" in active.json()
    assert "updated_at" in active.json()
    assert "raw_payload" not in active.json()

    inactive = api_client.get(f"/jobs/{seed_jobs['inactive-job']}")
    assert inactive.status_code == 200
    assert inactive.json()["status"] == "inactive"
    assert inactive.json()["inactive_at"] is not None


def test_detail_not_found_and_malformed_uuid(
    api_client: TestClient,
    seed_jobs: dict[str, uuid.UUID],
) -> None:
    missing = api_client.get(f"/jobs/{uuid.uuid4()}")
    assert missing.status_code == 404
    assert missing.json() == {"detail": "Job not found"}

    malformed = api_client.get("/jobs/not-a-uuid")
    assert malformed.status_code == 422


@pytest.mark.parametrize(
    ("params", "field"),
    [
        ({"remote_type": "invalid"}, "remote_type"),
        ({"employment_type": "bad"}, "employment_type"),
        ({"eligible_country": "USA"}, "eligible_country"),
        ({"salary_currency": "US"}, "salary_currency"),
        ({"posted_after": "not-a-date"}, "posted_after"),
        ({"salary_min": "-1"}, "salary_min"),
        ({"page": "0"}, "page"),
        ({"page_size": "101"}, "page_size"),
        ({"q": "x" * 201}, "q"),
    ],
)
def test_validation_errors_return_422(
    api_client: TestClient,
    seed_jobs: dict[str, uuid.UUID],
    params: dict[str, str],
    field: str,
) -> None:
    response = api_client.get("/jobs", params=params)
    assert response.status_code == 422
    assert any(field in err["loc"] for err in response.json()["detail"])


def test_salary_without_currency_returns_422_on_salary_currency(
    api_client: TestClient,
    seed_jobs: dict[str, uuid.UUID],
) -> None:
    filter_response = api_client.get("/jobs", params={"salary_min": "100000"})
    assert filter_response.status_code == 422
    assert any(
        "salary_currency" in err["loc"] for err in filter_response.json()["detail"]
    )

    sort_response = api_client.get("/jobs", params={"sort": "salary_asc"})
    assert sort_response.status_code == 422
    assert any(
        "salary_currency" in err["loc"] for err in sort_response.json()["detail"]
    )


def test_salary_min_greater_than_max_returns_422(
    api_client: TestClient,
    seed_jobs: dict[str, uuid.UUID],
) -> None:
    response = api_client.get(
        "/jobs",
        params={
            "salary_min": "200000",
            "salary_max": "100000",
            "salary_currency": "USD",
        },
    )
    assert response.status_code == 422


def test_list_response_never_includes_raw_payload(
    api_client: TestClient,
    seed_jobs: dict[str, uuid.UUID],
) -> None:
    response = api_client.get("/jobs", params={"page_size": 100})
    assert response.status_code == 200
    for item in response.json()["items"]:
        assert "raw_payload" not in item


def test_query_plans_use_expected_indexes(
    db_session: Session,
    seed_jobs: dict[str, uuid.UUID],
) -> None:
    keyword_plan = db_session.execute(
        text(
            f"EXPLAIN SELECT id FROM jobs WHERE status = 'active' "
            f"AND {JOB_SEARCH_VECTOR_SQL} @@ websearch_to_tsquery('english', :q)"
        ),
        {"q": "python"},
    ).all()
    keyword_text = "\n".join(row[0] for row in keyword_plan)
    assert "to_tsvector" in keyword_text

    newest_plan = db_session.execute(
        text(
            "EXPLAIN SELECT id FROM jobs WHERE status = 'active' "
            "ORDER BY COALESCE(posted_at, discovered_at) DESC, id DESC"
        )
    ).all()
    newest_text = "\n".join(row[0] for row in newest_plan)
    assert "ix_jobs_status_posted_at_id" in newest_text or "Sort" in newest_text

    salary_plan = db_session.execute(
        text(
            "EXPLAIN SELECT id FROM jobs WHERE status = 'active' "
            "AND (salary_currency IS NULL OR salary_currency = 'USD') "
            "ORDER BY salary_min_annual ASC NULLS LAST, id ASC"
        )
    ).all()
    salary_text = "\n".join(row[0] for row in salary_plan)
    assert "ix_jobs_salary_currency_annual" in salary_text or "Sort" in salary_text
