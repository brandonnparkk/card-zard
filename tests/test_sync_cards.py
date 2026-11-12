"""Tests for sync_cards, the upsert-and-delete step of a load.

test_load_snapshot.py checks loading whole files. These tests call sync_cards
directly, to pin down batching, the counts it returns, and the two cases where
it must refuse to touch the table.
"""

import uuid
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from card_zard.snapshots.bulk_file import CardRow, to_card_row
from card_zard.snapshots.loader import CardSync, sync_cards

pytestmark = pytest.mark.db


def make_row(**fields: Any) -> CardRow:
    record: dict[str, Any] = {
        "oracle_id": str(uuid.uuid4()),
        "name": "Test Card",
        "layout": "normal",
        "cmc": 2,
        "type_line": "Creature — Human",
        "oracle_text": "Vigilance",
        "color_identity": ["W"],
        "keywords": ["Vigilance"],
        "legalities": {"commander": "legal"},
    }
    record.update(fields)
    return to_card_row(record)


def names(session: Session) -> set[str]:
    return set(session.execute(text("SELECT name FROM cards")).scalars())


def test_rows_spanning_several_batches_are_all_inserted(session: Session) -> None:
    rows = [make_row(name=f"Card {n}") for n in range(5)]

    result = sync_cards(session, rows, batch_size=2)

    assert result == CardSync(upserted=5, deleted=0)
    assert names(session) == {f"Card {n}" for n in range(5)}


def test_the_result_counts_deleted_cards(session: Session) -> None:
    kept, dropped_1, dropped_2 = make_row(), make_row(), make_row()
    sync_cards(session, [kept, dropped_1, dropped_2])

    result = sync_cards(session, [kept])

    assert result == CardSync(upserted=1, deleted=2)


def test_an_upsert_overwrites_every_column(session: Session) -> None:
    original = make_row(name="Old", produced_mana=["W"])
    sync_cards(session, [original])
    changed = make_row(
        oracle_id=str(original["oracle_id"]),
        name="New",
        cmc=5,
        produced_mana=["U", "B"],
        legalities={"commander": "banned"},
    )

    sync_cards(session, [changed])

    row = session.execute(text("SELECT * FROM cards")).one()
    assert row.name == "New"
    assert row.mana_value == 5
    assert row.produced_mana == ["U", "B"]
    assert row.commander_legality == "banned"


def test_a_duplicate_oracle_id_is_refused_before_writing(session: Session) -> None:
    sync_cards(session, [make_row(name="Existing")])
    duplicate = make_row(name="Twice")

    with pytest.raises(ValueError, match=r"'Twice'.*more than once"):
        sync_cards(session, [make_row(name="New"), duplicate, duplicate])

    # The duplicate was in the first batch, so nothing was written or deleted.
    assert names(session) == {"Existing"}


def test_an_empty_file_is_refused_instead_of_deleting_everything(
    session: Session,
) -> None:
    sync_cards(session, [make_row(name="Existing")])

    with pytest.raises(ValueError, match="no game cards"):
        sync_cards(session, [])

    assert names(session) == {"Existing"}
