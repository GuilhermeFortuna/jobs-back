"""Unit tests for cross-provider dedup key derivation."""

from __future__ import annotations

import pytest

from jobs_back.normalization.dedup import (
    derive_dedup_key,
    eligibility_token,
    normalize_company,
    normalize_title,
)
from tests.helpers.discovery import make_job_result


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Acme Corp", "acme corp"),
        ("ACME Corp., Inc.", "acme corp"),
        ("Globex GmbH", "globex"),
        ("Initech Ltd.", "initech"),
        ("Umbrella Corp LLC", "umbrella corp"),
    ],
)
def test_normalize_company_strips_legal_suffixes(raw: str, expected: str) -> None:
    assert normalize_company(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Senior Backend Engineer", "senior backend engineer"),
        ("Backend Engineer (m/f/d)", "backend engineer"),
        ("Python Developer [Remote]", "python developer"),
        ("Staff Engineer (US Only)", "staff engineer"),
    ],
)
def test_normalize_title_preserves_seniority_strips_qualifiers(
    raw: str, expected: str
) -> None:
    assert normalize_title(raw) == expected


def test_seniority_and_numbering_produce_distinct_keys() -> None:
    senior = make_job_result(title="Senior Backend Engineer")
    junior = make_job_result(title="Backend Engineer", provider_job_id="junior")
    engineer_i = make_job_result(title="Engineer I", provider_job_id="i")
    engineer_ii = make_job_result(title="Engineer II", provider_job_id="ii")

    keys = {
        derive_dedup_key(item) for item in (senior, junior, engineer_i, engineer_ii)
    }
    assert len(keys) == 4


def test_cross_provider_variants_share_dedup_key() -> None:
    himalayas = make_job_result(
        provider="himalayas",
        provider_job_id="h-1",
        company="Acme Corp, Inc.",
        title="Senior Python Developer [Remote]",
    )
    remoteok = make_job_result(
        provider="remoteok",
        provider_job_id="r-1",
        company="ACME CORP",
        title="Senior Python Developer",
        job_url="https://remoteok.com/jobs/1",
        apply_url="https://remoteok.com/jobs/1/apply",
    )
    assert derive_dedup_key(himalayas) == derive_dedup_key(remoteok)


def test_different_regions_stay_distinct() -> None:
    us = make_job_result(
        provider_job_id="us",
        eligible_country_codes=["US"],
        location_text="Remote - US",
    )
    eu = make_job_result(
        provider_job_id="eu",
        eligible_country_codes=["DE", "FR"],
        location_text="Remote - EU",
    )
    assert derive_dedup_key(us) != derive_dedup_key(eu)


def test_eligibility_token_prefers_country_codes() -> None:
    token = eligibility_token(
        "remote",
        ["US", "CA"],
        "Remote - Worldwide",
    )
    assert token == "remote:CA,US"


def test_empty_company_or_title_uses_unique_fallback() -> None:
    empty_company = make_job_result(company="   ", provider_job_id="a")
    empty_title = make_job_result(title="!!!", provider_job_id="b")
    assert derive_dedup_key(empty_company).startswith("unique:")
    assert derive_dedup_key(empty_title).startswith("unique:")


@pytest.mark.parametrize(
    ("title", "company"),
    [
        ("Full Stack Developer", "Stripe"),
        ("DevOps Engineer", "GitLab"),
        ("Product Designer", "Figma"),
        ("Data Engineer", "Snowflake"),
        ("Frontend Engineer", "Vercel"),
        ("Backend Engineer", "Shopify"),
    ],
)
def test_realistic_titles_normalize_deterministically(title: str, company: str) -> None:
    first = derive_dedup_key(
        make_job_result(title=title, company=company, provider_job_id="1")
    )
    second = derive_dedup_key(
        make_job_result(
            title=f"{title} (m/f/d)",
            company=f"{company}, Inc.",
            provider_job_id="2",
        )
    )
    assert first == second
