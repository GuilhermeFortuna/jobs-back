"""Schema coverage for JE-011 search and result fields."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from jobs_back.schemas.discovery import JobResult, SearchFilters


def test_search_filters_schema_includes_location() -> None:
    schema = SearchFilters.model_json_schema()
    assert "location" in schema["properties"]


def test_job_result_schema_includes_ranking_fields() -> None:
    schema = JobResult.model_json_schema()
    assert "relevance_score" in schema["properties"]
    assert "matched_skills" in schema["properties"]


def test_search_filters_reject_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        SearchFilters.model_validate({"query": "python", "unknown": "nope"})


def test_search_filters_require_a_substantive_provider_criterion() -> None:
    assert not SearchFilters().has_search_criteria()
    assert not SearchFilters(providers=["remoteok"]).has_search_criteria()
    assert not SearchFilters(sort="newest").has_search_criteria()
    assert SearchFilters(query="python").has_search_criteria()
    assert SearchFilters(location="Lisbon").has_search_criteria()
    assert SearchFilters(country="Brazil").has_search_criteria()
    assert SearchFilters(worldwide=True).has_search_criteria()
    assert SearchFilters(seniority=["Senior"]).has_search_criteria()
    assert SearchFilters(employment_types=["Full Time"]).has_search_criteria()
    assert SearchFilters(minimum_salary=100_000).has_search_criteria()
    assert SearchFilters(salary_stated_only=True).has_search_criteria()
    assert SearchFilters(posted_within_days=7).has_search_criteria()


def test_search_filters_schema_includes_stated_salary_filter() -> None:
    schema = SearchFilters.model_json_schema()
    assert "salary_stated_only" in schema["properties"]
