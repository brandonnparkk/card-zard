"""Database plumbing: the declarative Base and engine/session factories.

Models live next to the code that uses them (for example
`card_zard.snapshots.models`) and subclass `Base` from here.
"""

import os

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def database_url() -> str:
    """The `DATABASE_URL` environment variable.

    There is deliberately no default: a default would have to contain a
    password, and passwords never go in the repo. Locally the value comes
    from the gitignored `.env` file (see `.env.example`); in a deployment it
    comes from the host's secret settings.
    """
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Copy .env.example to .env and fill it in."
        )
    return url


def make_engine(url: str | None = None) -> Engine:
    return create_engine(url or database_url())


def make_sessionmaker(engine: Engine | None = None) -> sessionmaker[Session]:
    return sessionmaker(engine or make_engine())
