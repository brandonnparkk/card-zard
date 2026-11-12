from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import create_engine, pool

# Importing the models registers their tables on Base.metadata.
import card_zard.snapshots.models  # noqa: F401
from card_zard.db import Base, database_url

# Locally, DATABASE_URL comes from the gitignored .env file. python-dotenv is a
# dev dependency: a deployment installs without it and sets DATABASE_URL from
# its secret settings, so a missing package just means "nothing to load".
try:
    from dotenv import load_dotenv
except ImportError:
    pass
else:
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging. Existing loggers are left
# alone so running migrations from pytest doesn't silence other loggers.
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def get_url() -> str:
    """`sqlalchemy.url` if a caller set it (the tests do), else DATABASE_URL."""
    return config.get_main_option("sqlalchemy.url") or database_url()


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode, emitting SQL instead of running it."""
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode against a live database."""
    connectable = create_engine(get_url(), poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
