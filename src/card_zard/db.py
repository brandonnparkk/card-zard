"""Database plumbing: the declarative Base and engine/session factories.

Models live next to the code that uses them (for example
`card_zard.snapshots.models`) and subclass `Base` from here.
"""

import os

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# Matches .env.example and docker-compose.yml.
DEFAULT_DATABASE_URL = (
    "postgresql+psycopg://card_zard:card_zard@localhost:5433/card_zard"
)


class Base(DeclarativeBase):
    pass


def database_url() -> str:
    """The `DATABASE_URL` environment variable, or the local Docker default."""
    return os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)


def make_engine(url: str | None = None) -> Engine:
    return create_engine(url or database_url())


def make_sessionmaker(engine: Engine | None = None) -> sessionmaker[Session]:
    return sessionmaker(engine or make_engine())
