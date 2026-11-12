"""Load a Scryfall bulk file into the `cards` table (ADR-0013).

A load makes `cards` mirror the file exactly: every game card in the file is
inserted or updated by oracle_id, and every Card that isn't in the file is
deleted. It all happens inside the caller's transaction, so a failure halfway
through leaves the table as it was, once the caller rolls back.

Phase 2 of ticket #2 covers syncing the cards. Phase 3 adds the Snapshot row,
the same-file skip, and makes load_snapshot return the Snapshot.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from itertools import batched
from pathlib import Path
from typing import Any, cast
from uuid import UUID

from sqlalchemy import CursorResult, Uuid, any_, bindparam, delete
from sqlalchemy.dialects.postgresql import ARRAY, Insert, insert
from sqlalchemy.orm import Session

from card_zard.snapshots.bulk_file import CardRow, read_card_rows
from card_zard.snapshots.models import Card

# Rows per INSERT. Each row sends 11 values, and Postgres allows at most 65,535
# parameters in one statement, so batches must stay under about 5,900 rows.
# 1,000 keeps each statement small, and the full file still takes only ~36.
BATCH_SIZE = 1000


@dataclass(frozen=True)
class CardSync:
    """What a sync changed, for logging and for phase 3's Snapshot."""

    upserted: int
    deleted: int


def load_snapshot(session: Session, path: Path) -> None:
    """Make the `cards` table match the bulk file at `path`.

    Never commits: the caller owns the transaction, normally with
    `with session.begin(): load_snapshot(session, path)`. If anything raises,
    the caller's rollback undoes every batch already written.
    """
    sync_cards(session, read_card_rows(path))


def sync_cards(
    session: Session, rows: Iterable[CardRow], *, batch_size: int = BATCH_SIZE
) -> CardSync:
    """Upsert `rows` into `cards`, then delete every Card not among them.

    Raises ValueError without deleting anything if `rows` is empty or names
    the same oracle_id twice.
    """
    seen: set[UUID] = set()
    upserted = 0

    # batched() (Python 3.12+) groups the rows into tuples of batch_size. The
    # rows come from a generator, so only one batch is in memory at a time.
    # strict=False because the last batch is allowed to be short.
    for batch in batched(rows, batch_size, strict=False):
        for row in batch:
            # Postgres rejects an upsert that touches the same row twice in one
            # statement, and a duplicate means the file is wrong anyway. Check
            # here so the error names the card instead of quoting SQL.
            if row["oracle_id"] in seen:
                raise ValueError(
                    f"oracle_id {row['oracle_id']} ({row['name']!r}) "
                    "appears more than once"
                )
            seen.add(row["oracle_id"])

        session.execute(_UPSERT, list(batch))
        upserted += len(batch)

    # Safety net. Deleting "every card not in the file" with an empty file
    # would wipe the table. A truncated download is far likelier than Scryfall
    # really having zero cards, so refuse instead (ADR-0008: don't guess).
    if not seen:
        raise ValueError("the bulk file contains no game cards; refusing to load")

    return CardSync(upserted=upserted, deleted=_delete_cards_not_in(session, seen))


def _delete_cards_not_in(session: Session, keep: set[UUID]) -> int:
    """Delete every Card whose oracle_id isn't in `keep`; return how many."""
    # The ids go in as ONE parameter, a uuid[] array:
    #   DELETE FROM cards WHERE NOT (oracle_id = ANY(:keep_ids))
    # The obvious `Card.oracle_id.not_in(keep)` would send ~35,000 separate
    # parameters instead, which is slow and close to Postgres's 65,535 limit.
    keep_ids = bindparam("keep_ids", list(keep), type_=ARRAY(Uuid()))
    statement = delete(Card).where(~(Card.oracle_id == any_(keep_ids)))

    # synchronize_session=False: by default SQLAlchemy also updates any Card
    # objects loaded in this session, and since it can't evaluate ANY() in
    # Python it would first SELECT the doomed ids. The loader never loads Card
    # objects, so there's nothing to update.
    result = session.execute(
        statement, execution_options={"synchronize_session": False}
    )
    # session.execute is typed as returning a generic Result, but a DELETE
    # really returns a CursorResult, which is the type that has .rowcount.
    return cast(CursorResult[Any], result).rowcount


def _upsert_statement() -> Insert:
    """INSERT ... ON CONFLICT (oracle_id) DO UPDATE every other column.

    `excluded` is Postgres's name for the row we tried to insert, so
    `name = excluded.name` means "take the new value from the file".
    """
    statement = insert(Card)
    updatable = [c.name for c in Card.__table__.columns if c.name != "oracle_id"]
    return statement.on_conflict_do_update(
        index_elements=[Card.oracle_id],
        set_={name: statement.excluded[name] for name in updatable},
    )


# Built once at import time; it's the same statement for every batch. Passing
# it a list of dicts makes SQLAlchemy send one multi-row INSERT per batch.
_UPSERT = _upsert_statement()
