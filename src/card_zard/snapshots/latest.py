"""Find the Snapshot the `cards` table currently holds."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from card_zard.snapshots.models import Snapshot


def latest_snapshot(session: Session) -> Snapshot | None:
    """The most recently recorded Snapshot, or None if nothing was ever loaded.

    "Latest" means the highest id: ids only go up, and each load adds its
    Snapshot last, in the same transaction as the cards. So inside one
    transaction, this is always the Snapshot the `cards` table matches.
    """
    return session.scalars(
        select(Snapshot).order_by(Snapshot.id.desc()).limit(1)
    ).first()
