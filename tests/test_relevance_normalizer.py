"""Unit tests for skill token normalization."""

from __future__ import annotations

import pytest

from jobs_back.search.relevance import normalize_token


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("Python", "python"),
        ("NODE.JS", "nodejs"),
        ("Node.js", "nodejs"),
        ("  React  ", "react"),
        ("react.js", "react"),
        ("C++", "c"),
        ("k8s", "kubernetes"),
        ("Kubernetes", "kubernetes"),
        ("Postgres", "postgresql"),
        ("PostgreSQL", "postgresql"),
        ("JavaScript", "javascript"),
        ("JS", "javascript"),
        ("foo-bar_baz", "foobarbaz"),
        ("...", ""),
        ("   ", ""),
        ("---", ""),
    ],
)
def test_normalize_token(label: str, expected: str) -> None:
    assert normalize_token(label.strip()) == expected
