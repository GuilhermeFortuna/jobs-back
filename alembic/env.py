from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

import jobs_back.models  # noqa: F401 — register models on Base.metadata
from jobs_back.config import get_settings
from jobs_back.db import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# PostgreSQL normalizes the full-text expression with implicit casts, which makes
# Alembic report a false expression change. Revision 003 remains authoritative for
# this one migration-managed index; every ordinary index is still compared.
_MIGRATION_MANAGED_INDEXES = {"ix_jobs_search_vector"}


def include_object(
    _object: object,
    name: str | None,
    type_: str,
    _reflected: bool,
    _compare_to: object | None,
) -> bool:
    return not (type_ == "index" and name in _MIGRATION_MANAGED_INDEXES)


config.set_main_option("sqlalchemy.url", get_settings().database_url)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
