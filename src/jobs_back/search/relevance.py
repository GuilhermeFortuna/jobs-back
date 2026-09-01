"""Skill token normalization shared by profile storage (JE-010) and ranking (JE-011)."""

from __future__ import annotations

import re

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

_PUNCTUATION_AND_SEPARATORS = re.compile(r"[\s._\-/\\+#]+")


def normalize_token(label: str) -> str:
    """Return the normalized matching token for a skill label, or an empty string."""
    folded = label.casefold()
    stripped = _PUNCTUATION_AND_SEPARATORS.sub("", folded)
    if not stripped:
        return ""
    return TOKEN_ALIASES.get(stripped, stripped)
