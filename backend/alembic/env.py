"""Alembic environment. The database URL comes from settings (env vars), never from alembic.ini."""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from app.core.config import get_settings
from app.db import models_registry  # noqa: F401 - imports every model so metadata is complete
from app.db.base import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# A caller (e.g. the test harness) may pass the URL explicitly via
# config.attributes["database_url"]; otherwise DATABASE_URL from the environment.
_url: str | None = config.attributes.get("database_url")
if _url is None:
    _secret = get_settings().database_url
    if _secret is None:
        raise RuntimeError("DATABASE_URL must be set to run migrations")
    _url = _secret.get_secret_value()
# Escape '%' because ConfigParser treats it as interpolation.
config.set_main_option("sqlalchemy.url", _url.replace("%", "%%"))

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
