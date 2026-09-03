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
