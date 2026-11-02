"""Alembic environment for the CTFd database (standalone: the deploy pipeline runs `alembic` directly).

The connection URL comes from DATABASE_URL (postgresql+psycopg://user:password@host:port/dbname).
"""
import logging
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)
logger = logging.getLogger("alembic.env")

config.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"].replace("%", "%%"))

# The ORM models live in CTFd/models; autogenerate is not used by this team (revisions are written by hand).
target_metadata = None


def run_migrations_offline():
    """Emit the SQL of the migrations instead of running them (`alembic upgrade --sql`)."""
    context.configure(url=config.get_main_option("sqlalchemy.url"), target_metadata=target_metadata,
                      literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(config.get_section(config.config_ini_section), prefix="sqlalchemy.",
                                     poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
