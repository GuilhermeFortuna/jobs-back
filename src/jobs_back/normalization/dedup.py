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
    lowered = _BRACKETED_RE.sub("", lowered)
    lowered = _PARENTHETICAL_RE.sub("", lowered)
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
