"""Skill token normalization and deterministic relevance scoring (JE-010 / JE-011)."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from jobs_back.schemas.discovery import JobResult

# Curated alias table: normalized variant -> canonical token.
# Convenience for common abbreviations, not an exhaustive taxonomy (ADR-002).
TOKEN_ALIASES: dict[str, str] = {
    "js": "javascript",
    "javascript": "javascript",
    "k8s": "kubernetes",
    "kubernetes": "kubernetes",
    "postgres": "postgresql",
    "postgresql": "postgresql",
    "react": "react",
    "reactjs": "react",
    "nodejs": "nodejs",
}

# Title match outranks description match for the same term.
WEIGHT_TITLE = 10.0
WEIGHT_COMPANY = 5.0
WEIGHT_LOCATION = 3.0
WEIGHT_DESCRIPTION = 1.0

# Skill hits use the same field ordering; kept separate so tests can reason about caps.
SKILL_WEIGHT_TITLE = 8.0
SKILL_WEIGHT_COMPANY = 4.0
SKILL_WEIGHT_LOCATION = 2.0
SKILL_WEIGHT_DESCRIPTION = 1.0

# A long skill list cannot swamp the query contribution.
MAX_SKILL_CONTRIBUTION = 20.0

# Recency is a bounded nudge that cannot reorder unequal match strengths.
MAX_RECENCY_BONUS = 2.0
RECENCY_HALF_LIFE_DAYS = 30.0

_FIELD_WEIGHTS: Mapping[str, float] = {
    "title": WEIGHT_TITLE,
    "company": WEIGHT_COMPANY,
    "location": WEIGHT_LOCATION,
    "description": WEIGHT_DESCRIPTION,
}

_SKILL_FIELD_WEIGHTS: Mapping[str, float] = {
    "title": SKILL_WEIGHT_TITLE,
    "company": SKILL_WEIGHT_COMPANY,
    "location": SKILL_WEIGHT_LOCATION,
    "description": SKILL_WEIGHT_DESCRIPTION,
}

_PUNCTUATION_AND_SEPARATORS = re.compile(r"[\s._\-/\\+#]+")
_WORD_PATTERN = re.compile(r"[a-zA-Z0-9]+")


def normalize_token(label: str) -> str:
    """Return the normalized matching token for a skill label, or an empty string."""
    folded = label.casefold()
    stripped = _PUNCTUATION_AND_SEPARATORS.sub("", folded)
    if not stripped:
        return ""
    return TOKEN_ALIASES.get(stripped, stripped)


def normalize_query_tokens(query: str) -> list[str]:
    """Return distinct normalized query tokens in first-seen order."""
    seen: set[str] = set()
    tokens: list[str] = []
    for raw in query.split():
        token = normalize_token(raw)
        if token and token not in seen:
            seen.add(token)
            tokens.append(token)
    return tokens


def extract_text_tokens(text: str | None) -> set[str]:
    """Word-boundary tokens from searchable text, each normalized."""
    if not text:
        return set()
    return {
        token
        for word in _WORD_PATTERN.findall(text)
        if (token := normalize_token(word))
    }


def normalize_location_text(text: str) -> str:
    """Collapse location text for substring containment checks."""
    return _PUNCTUATION_AND_SEPARATORS.sub("", text.casefold())


def _field_token_sets(job: JobResult) -> dict[str, set[str]]:
    return {
        "title": extract_text_tokens(job.title),
        "company": extract_text_tokens(job.company),
        "location": extract_text_tokens(job.location_text),
        "description": extract_text_tokens(job.description),
    }


def _token_in_fields(token: str, field_tokens: Mapping[str, set[str]]) -> bool:
    return any(token in tokens for tokens in field_tokens.values())


def _field_weight_for_token(
    token: str,
    field_tokens: Mapping[str, set[str]],
    weights: Mapping[str, float],
) -> float:
    total = 0.0
    for field, tokens in field_tokens.items():
        if token in tokens:
            total += weights[field]
    return total


def job_matches_query(job: JobResult, query_tokens: Sequence[str]) -> bool:
    """Every distinct query token must match at least one searchable field."""
    if not query_tokens:
        return True
    field_tokens = _field_token_sets(job)
    return all(_token_in_fields(token, field_tokens) for token in query_tokens)


def job_matches_location(job: JobResult, location_filter: str) -> bool:
    """Location filter matches normalized location text via containment."""
    if not location_filter:
        return True
    if not job.location_text:
        return False
    normalized_job = normalize_location_text(job.location_text)
    normalized_filter = normalize_location_text(location_filter)
    return normalized_filter in normalized_job


def _query_contribution(
    query_tokens: Sequence[str],
    field_tokens: Mapping[str, set[str]],
) -> float:
    if not query_tokens:
        return 0.0

    matched = 0
    raw_hits = 0.0
    for token in query_tokens:
        weight = _field_weight_for_token(token, field_tokens, _FIELD_WEIGHTS)
        if weight:
            matched += 1
            raw_hits += weight

    coverage = matched / len(query_tokens)
    return raw_hits * coverage


def _skill_contribution(
    profile_skills: Sequence[tuple[str, str]],
    field_tokens: Mapping[str, set[str]],
) -> tuple[float, list[str]]:
    total = 0.0
    matched_labels: list[str] = []
    for label, token in profile_skills:
        weight = _field_weight_for_token(token, field_tokens, _SKILL_FIELD_WEIGHTS)
        if weight:
            total += weight
            matched_labels.append(label)
    return min(total, MAX_SKILL_CONTRIBUTION), matched_labels


def _recency_bonus(job: JobResult, *, now: datetime) -> float:
    if job.posted_at is None:
        return 0.0
    posted = (
        job.posted_at if job.posted_at.tzinfo else job.posted_at.replace(tzinfo=UTC)
    )
    reference = now if now.tzinfo else now.replace(tzinfo=UTC)
    age_days = max(0.0, (reference - posted).total_seconds() / 86_400)
    decay = math.pow(0.5, age_days / RECENCY_HALF_LIFE_DAYS)
    return MAX_RECENCY_BONUS * decay


def score_job(
    job: JobResult,
    query_tokens: Sequence[str],
    profile_skills: Sequence[tuple[str, str]],
    *,
    now: datetime,
) -> tuple[float, list[str]]:
    """Pure relevance score and matched skill labels in profile order."""
    field_tokens = _field_token_sets(job)
    query_score = _query_contribution(query_tokens, field_tokens)
    skill_score, matched_labels = _skill_contribution(profile_skills, field_tokens)
    recency = _recency_bonus(job, now=now)
    return query_score + skill_score + recency, matched_labels
