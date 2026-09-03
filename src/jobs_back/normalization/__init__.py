"""Normalization helpers for provider-neutral job records."""

from jobs_back.normalization.compensation import (
    annualize_amount,
    annualize_bounds,
    quantize_money,
)
from jobs_back.normalization.dedup import (
    derive_dedup_key,
    eligibility_token,
    normalize_company,
    normalize_title,
)

__all__ = [
    "annualize_amount",
    "annualize_bounds",
    "derive_dedup_key",
    "eligibility_token",
    "normalize_company",
    "normalize_title",
    "quantize_money",
]
