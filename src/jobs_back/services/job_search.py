"""Job search query construction and execution."""

from __future__ import annotations

import math
from uuid import UUID

from sqlalchemy import Select, and_, case, func, or_, select
from sqlalchemy.orm import Session

from jobs_back.models.enums import JobStatus
from jobs_back.models.job import Job
from jobs_back.schemas.job import JobDetail, JobSummary
from jobs_back.schemas.job_search import JobPage, JobSearchParams, JobSort
from jobs_back.search.constants import job_search_vector, websearch_tsquery


def get_job_by_id(session: Session, job_id: UUID) -> JobDetail | None:
    """Return job detail by ID regardless of status."""
    job = session.get(Job, job_id)
    if job is None:
        return None
    return JobDetail.model_validate(job)


def search_jobs(session: Session, params: JobSearchParams) -> JobPage:
    """Search active jobs with filters, sorting, and pagination."""
    base = select(Job).where(Job.status == JobStatus.ACTIVE.value)
    filtered = _apply_filters(base, params)

    total = session.scalar(select(func.count()).select_from(filtered.subquery()))
    total = int(total or 0)
    total_pages = 0 if total == 0 else math.ceil(total / params.page_size)

    ordered = _apply_sort(filtered, params)
    offset = (params.page - 1) * params.page_size
    page_query = ordered.offset(offset).limit(params.page_size)
    rows = session.scalars(page_query).all()

    return JobPage(
        items=[JobSummary.model_validate(row) for row in rows],
        page=params.page,
        page_size=params.page_size,
        total=total,
        total_pages=total_pages,
    )


def _apply_filters(stmt: Select, params: JobSearchParams) -> Select:
    conditions = []

    if params.q:
        vector = job_search_vector()
        conditions.append(vector.op("@@")(websearch_tsquery(params.q)))

    if params.location:
        pattern = f"%{params.location}%"
        conditions.append(
            or_(
                Job.location_text.ilike(pattern),
                Job.city.ilike(pattern),
                Job.region.ilike(pattern),
                Job.country_code.ilike(pattern),
            )
        )

    if params.remote_type:
        conditions.append(
            Job.remote_type.in_([value.value for value in params.remote_type])
        )

    if params.employment_type:
        conditions.append(
            Job.employment_type.in_([value.value for value in params.employment_type])
        )

    if params.provider:
        conditions.append(Job.provider.in_(params.provider))

    if params.eligible_country:
        country_conditions = []
        for code in params.eligible_country:
            country_conditions.append(
                and_(
                    Job.eligible_country_codes.is_not(None),
                    or_(
                        Job.eligible_country_codes.contains([code]),
                        Job.eligible_country_codes == [],
                    ),
                )
            )
        conditions.append(or_(*country_conditions))

    if params.posted_after is not None:
        conditions.append(
            and_(
                Job.posted_at.is_not(None),
                Job.posted_at >= params.posted_after,
            )
        )

    if params.salary_currency is not None and (
        params.salary_min is not None
        or params.salary_max is not None
        or params.sort in (JobSort.SALARY_ASC, JobSort.SALARY_DESC)
    ):
        if params.sort in (JobSort.SALARY_ASC, JobSort.SALARY_DESC):
            conditions.append(
                or_(
                    Job.salary_currency.is_(None),
                    Job.salary_currency == params.salary_currency,
                )
            )
        else:
            conditions.append(Job.salary_currency == params.salary_currency)

        if params.salary_min is not None or params.salary_max is not None:
            conditions.append(
                or_(
                    Job.salary_min_annual.is_not(None),
                    Job.salary_max_annual.is_not(None),
                )
            )

        if params.salary_min is not None or params.salary_max is not None:
            effective_min = func.coalesce(
                Job.salary_min_annual,
                Job.salary_max_annual,
            )
            effective_max = func.coalesce(
                Job.salary_max_annual,
                Job.salary_min_annual,
            )
            if params.salary_max is not None:
                conditions.append(effective_min <= params.salary_max)
            if params.salary_min is not None:
                conditions.append(effective_max >= params.salary_min)

    if conditions:
        stmt = stmt.where(and_(*conditions))
    return stmt


def _apply_sort(stmt: Select, params: JobSearchParams) -> Select:
    if params.sort == JobSort.NEWEST:
        return stmt.order_by(
            func.coalesce(Job.posted_at, Job.discovered_at).desc(),
            Job.id.desc(),
        )

    assert params.salary_currency is not None
    currency = params.salary_currency
    effective_lower = func.coalesce(Job.salary_min_annual, Job.salary_max_annual)
    effective_upper = func.coalesce(Job.salary_max_annual, Job.salary_min_annual)
    has_annual = or_(
        Job.salary_min_annual.is_not(None),
        Job.salary_max_annual.is_not(None),
    )
    comparable = and_(
        has_annual,
        Job.salary_currency == currency,
    )

    if params.sort == JobSort.SALARY_ASC:
        sort_key = case(
            (comparable, effective_lower),
            else_=None,
        )
        return stmt.order_by(
            sort_key.asc().nulls_last(),
            Job.id.asc(),
        )

    if params.sort == JobSort.SALARY_DESC:
        sort_key = case(
            (comparable, effective_upper),
            else_=None,
        )
        return stmt.order_by(
            sort_key.desc().nulls_last(),
            Job.id.desc(),
        )

    raise AssertionError(f"Unhandled sort: {params.sort}")
