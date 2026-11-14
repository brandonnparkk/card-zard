"""Database sessions for API requests."""

from collections.abc import Iterator
from functools import cache

from sqlalchemy.orm import Session, sessionmaker

from card_zard.db import make_engine, make_sessionmaker


@cache
def _sessionmaker() -> sessionmaker[Session]:
    """Built on first use, not at import time.

    So importing the app (for /health, or in tests that replace get_session)
    doesn't need DATABASE_URL. @cache makes it one engine, and one connection
    pool, for the whole process.
    """
    # REPEATABLE READ: every query in a request sees the database as it was
    # when the request's first query ran. Under Postgres's default (READ
    # COMMITTED) a load committing between "which Snapshot?" and "which
    # Cards?" could mix two Snapshots in one Analysis.
    engine = make_engine().execution_options(isolation_level="REPEATABLE READ")
    return make_sessionmaker(engine)


def get_session() -> Iterator[Session]:
    """One Session, in one transaction, per request.

    FastAPI runs the code before `yield` when a request comes in and the rest
    (closing the transaction and Session) after the response is built.
    Requests only read, so the commit at the end changes nothing.
    """
    with _sessionmaker()() as session, session.begin():
        yield session
