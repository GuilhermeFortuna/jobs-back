"""Shared constants for job full-text search (migration + query must match)."""

from sqlalchemy import ColumnElement, func, literal_column

# SQL expression used identically in Alembic GIN index and runtime queries.
JOB_SEARCH_VECTOR_SQL = (
    "to_tsvector('english', "
    "coalesce(title, '') || ' ' || "
    "coalesce(company, '') || ' ' || "
    "coalesce(description, ''))"
)


def job_search_vector() -> ColumnElement:
    """SQLAlchemy expression for the English-weighted job search vector."""
    return literal_column(JOB_SEARCH_VECTOR_SQL)


def websearch_tsquery(query: str) -> ColumnElement:
    """Parameterized websearch_to_tsquery for keyword search."""
    return func.websearch_to_tsquery("english", query)
