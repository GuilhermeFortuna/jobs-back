"""Profile skill validation and token derivation."""

from __future__ import annotations

from jobs_back.search.relevance import normalize_token
from jobs_back.services.exceptions import InvalidSkillsError

MAX_SKILLS = 50
MIN_LABEL_LENGTH = 1
MAX_LABEL_LENGTH = 60


def skills_from_labels(labels: list[str]) -> list[dict[str, str]]:
    """Validate labels and return stored skill objects with server-derived tokens."""
    if len(labels) > MAX_SKILLS:
        raise InvalidSkillsError(f"At most {MAX_SKILLS} skills are allowed per profile")

    stored: list[dict[str, str]] = []
    seen_tokens: dict[str, str] = {}

    for raw_label in labels:
        label = raw_label.strip()
        if not (MIN_LABEL_LENGTH <= len(label) <= MAX_LABEL_LENGTH):
            raise InvalidSkillsError(
                f"Skill label must be {MIN_LABEL_LENGTH} to {MAX_LABEL_LENGTH} "
                f"characters after trimming: {label!r}"
            )

        token = normalize_token(label)
        if not token:
            raise InvalidSkillsError(
                f"Skill label normalizes to an empty token: {label!r}"
            )

        if token in seen_tokens:
            first_label = seen_tokens[token]
            raise InvalidSkillsError(
                f'Duplicate skill token "{token}": "{first_label}" and "{label}"'
            )

        seen_tokens[token] = label
        stored.append({"label": label, "token": token})

    return stored
