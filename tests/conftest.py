"""Shared fixtures for tests that need the Postgres test database.

Tests that use these fixtures should be marked `@pytest.mark.db`. They need
the Docker database running (`docker compose up -d db`).
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from dotenv import load_dotenv
from sqlalchemy import Engine, create_engine, make_url, text
from sqlalchemy.orm import Session

REPO_ROOT = Path(__file__).resolve().parent.parent

# Locally, TEST_DATABASE_URL comes from the gitignored .env file. Variables
# already set in the environment win (load_dotenv doesn't override them), which
# is how CI supplies its own. No .env file is fine: this is then a no-op.
load_dotenv(REPO_ROOT / ".env")


def _test_database_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.fail(
            "TEST_DATABASE_URL is not set. Copy .env.example to .env and fill it in.",
            pytrace=False,
        )
    return url


def _reset_schema(engine: Engine) -> None:
    """Drop every table, type and extension, including `alembic_version`."""
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))


def _upgrade_to_head(url: str) -> None:
    """Run `alembic upgrade head`, the same migrations a developer runs."""
    config = Config(str(REPO_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")


@pytest.fixture(scope="session")
def db_engine() -> Iterator[Engine]:
    """An engine for the test database, freshly reset and migrated to head.

    Runs once per test session, before the first test that needs it.
    """
    url = _test_database_url()
    database = make_url(url).database or ""
    # The schema is dropped below, so never point this at a real database.
    assert database.endswith("_test"), (
        f"TEST_DATABASE_URL must name a *_test database, not {database!r}"
    )

    engine = create_engine(url)
    _reset_schema(engine)
    _upgrade_to_head(url)
    yield engine
    engine.dispose()


@pytest.fixture
def session(db_engine: Engine) -> Iterator[Session]:
    """A Session whose changes are rolled back after the test.

    Code under test may call `session.commit()`: with "create_savepoint" the
    commit only releases a savepoint inside the outer transaction, which is
    still rolled back at the end.
    """
    with db_engine.connect() as connection:
        transaction = connection.begin()
        session = Session(bind=connection, join_transaction_mode="create_savepoint")
        try:
            yield session
        finally:
            session.close()
            transaction.rollback()
