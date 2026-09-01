"""Deterministic duplicate identity for cross-provider consolidation."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from jobs_back.schemas.discovery import JobResult

_DEDUP_DELIMITER = "\x1f"
_LEGAL_SUFFIXES = frozenset(
    {"inc", "ltd", "llc", "gmbh", "bv", "sa", "oy"},
)
_COLLAPSE_RE = re.compile(r"[\s\W_]+")
_BRACKETED_RE = re.compile(r"\[[^\]]*\]")
_PARENTHETICAL_RE = re.compile(r"\([^)]*\)")
_GENDER_MARKER_RE = re.compile(
    r"\(\s*[mfw]\s*/\s*[mfw]\s*/\s*[mfw]\s*\)",
    re.IGNORECASE,
)

# Tokens that distinguish one role from another. A bracketed or parenthetical
# qualifier containing any of these is unwrapped rather than dropped, so
# "Engineer (Senior)" and "Engineer (Junior)" keep distinct keys. Dropping them
# would merge distinct roles, which the Spec forbids outright.
_MEANINGFUL_QUALIFIER_TOKENS = frozenset(
    {
        "intern",
        "internship",
        "entry",
        "graduate",
        "junior",
        "jr",
        "associate",
        "mid",
        "intermediate",
        "senior",
        "sr",
        "staff",
        "principal",
        "lead",
        "head",
        "director",
        "i",
        "ii",
        "iii",
        "iv",
        "v",
    }
)
_DIGIT_RE = re.compile(r"\d")


def _qualifier_is_meaningful(inner: str) -> bool:
    if _DIGIT_RE.search(inner):
        return True
    tokens = _collapse(inner.lower()).split()
    return any(token in _MEANINGFUL_QUALIFIER_TOKENS for token in tokens)


def _strip_qualifiers(pattern: re.Pattern[str], text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        inner = match.group(0)[1:-1]
        return f" {inner} " if _qualifier_is_meaningful(inner) else " "

    return pattern.sub(replace, text)


def _collapse(text: str) -> str:
    return _COLLAPSE_RE.sub(" ", text).strip()


def normalize_company(name: str) -> str:
    collapsed = _collapse(name.lower())
    if not collapsed:
        return ""
    tokens = collapsed.split()
    while tokens and tokens[-1] in _LEGAL_SUFFIXES:
        tokens.pop()
    return " ".join(tokens)


def normalize_title(title: str) -> str:
    lowered = title.lower()
    lowered = _GENDER_MARKER_RE.sub("", lowered)
    lowered = _strip_qualifiers(_BRACKETED_RE, lowered)
    lowered = _strip_qualifiers(_PARENTHETICAL_RE, lowered)
    return _collapse(lowered)


def eligibility_token(
    remote_type: str,
    eligible_country_codes: list[str] | None,
    location_text: str | None,
) -> str:
    if eligible_country_codes:
        codes = ",".join(
            sorted(code.upper() for code in eligible_country_codes if code)
        )
        if codes:
            return f"{remote_type}:{codes}"
    if location_text:
        normalized = _collapse(location_text.lower())
        if normalized:
            return f"{remote_type}:{normalized}"
    return f"{remote_type}:any"


def derive_dedup_key(result: JobResult) -> str:
    company = normalize_company(result.company)
    title = normalize_title(result.title)
    if not company or not title:
        return f"unique:{result.provider}:{result.provider_job_id}"
    eligibility = eligibility_token(
        result.remote_type,
        result.eligible_country_codes,
        result.location_text,
    )
    return _DEDUP_DELIMITER.join((company, title, eligibility))
