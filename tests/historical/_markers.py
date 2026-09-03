"""Shared markers for superseded Batch 01 catalog tests."""

from __future__ import annotations

import pytest

BATCH01_SUPERSEDED = pytest.mark.skip(
    reason="Batch 01 catalog runtime superseded by ADR-001 (JE-004).",
)
