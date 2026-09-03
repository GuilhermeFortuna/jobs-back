"""Unit tests for deterministic relevance scoring rules."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from jobs_back.search.relevance import (
    MAX_RECENCY_BONUS,
    MAX_SKILL_CONTRIBUTION,
    SKILL_WEIGHT_DESCRIPTION,
    SKILL_WEIGHT_TITLE,
    extract_text_tokens,
    job_matches_query,
    normalize_query_tokens,
    score_job,
)
from tests.helpers.discovery import make_job_result

NOW = datetime(2026, 6, 1, tzinfo=UTC)


def _score(job, query_tokens=None, skills=None):
    return score_job(
        job,
        query_tokens or [],
        skills or [],
        now=NOW,
    )[0]


def test_title_match_outranks_description_only_match() -> None:
    title_job = make_job_result(
        title="Senior Python Engineer",
        description="General software role",
    )
    description_job = make_job_result(
        title="Software Engineer",
        description="Looking for Python experience",
    )
    query = normalize_query_tokens("python")
    assert _score(title_job, query) > _score(description_job, query)


def test_higher_query_coverage_outranks_lower_coverage() -> None:
    both_terms = make_job_result(
        title="Python Django Developer",
        description="Backend role",
    )
    one_term_twice = make_job_result(
        title="Python Python Developer",
        description="No django mention",
    )
    query = normalize_query_tokens("python django")
    assert _score(both_terms, query) > _score(one_term_twice, query)


def test_skill_contribution_is_capped() -> None:
    many_skills = [(f"Skill {index}", "python") for index in range(50)]
    job = make_job_result(title="Python Developer", description="python " * 50)
    score, matched = score_job(job, [], many_skills, now=NOW)
    assert len(matched) == 50
    uncapped = SKILL_WEIGHT_TITLE * 50
    assert uncapped > MAX_SKILL_CONTRIBUTION
    assert score <= MAX_SKILL_CONTRIBUTION + MAX_RECENCY_BONUS


def test_recency_cannot_reorder_different_match_strengths() -> None:
    strong = make_job_result(
        title="Python Engineer",
        description="python",
        posted_at=NOW - timedelta(days=120),
    )
    weak = make_job_result(
        title="Engineer",
        description="pythonic workflows only",
        posted_at=NOW - timedelta(days=1),
    )
    query = normalize_query_tokens("python")
    assert _score(strong, query) > _score(weak, query)


def test_empty_query_and_no_skills_uses_recency() -> None:
    older = make_job_result(posted_at=NOW - timedelta(days=90))
    newer = make_job_result(posted_at=NOW - timedelta(days=1))
    assert _score(newer) > _score(older)


def test_job_with_no_skill_matches_still_scores() -> None:
    job = make_job_result(title="Unrelated Role", description="No overlap")
    score, matched = score_job(job, [], [("Rust", "rust")], now=NOW)
    assert score >= 0
    assert matched == []


def test_alias_skill_matches_kubernetes_text() -> None:
    job = make_job_result(
        title="Platform Engineer",
        description="Manage Kubernetes clusters",
    )
    _, matched = score_job(job, [], [("k8s", "kubernetes")], now=NOW)
    assert matched == ["k8s"]


@pytest.mark.parametrize(
    ("text", "token", "expected"),
    [
        ("pythonic code", "python", False),
        ("category manager", "go", False),
        ("Python 3 developer", "python", True),
    ],
)
def test_word_boundary_matching(text: str, token: str, expected: bool) -> None:
    tokens = extract_text_tokens(text)
    assert (token in tokens) is expected


def test_query_membership_requires_every_token() -> None:
    job = make_job_result(title="Python Developer", description="Backend")
    assert job_matches_query(job, normalize_query_tokens("python"))
    assert not job_matches_query(job, normalize_query_tokens("python django"))


def test_matched_skills_preserve_profile_order() -> None:
    job = make_job_result(
        title="Python Django React Engineer",
        description="Full stack",
    )
    skills = [
        ("React", "react"),
        ("Python", "python"),
        ("Django", "django"),
    ]
    _, matched = score_job(job, [], skills, now=NOW)
    assert matched == ["React", "Python", "Django"]


def test_skill_field_weights_favor_title_over_description() -> None:
    title_job = make_job_result(title="Rust Engineer", description="Other things")
    description_job = make_job_result(title="Engineer", description="Rust systems")
    skills = [("Rust", "rust")]
    title_score = _score(title_job, skills=skills)
    description_score = _score(description_job, skills=skills)
    skill_gap = SKILL_WEIGHT_TITLE - SKILL_WEIGHT_DESCRIPTION
    assert title_score - description_score >= skill_gap
