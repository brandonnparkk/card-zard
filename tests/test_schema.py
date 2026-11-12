"""The schema that `alembic upgrade head` creates (issue #2, ADR-0013).

These tests use plain table and column names, so they check the database
itself and don't depend on how the models are written.
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy import Engine, Inspector, inspect, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Session
from sqlalchemy.types import TEXT

pytestmark = pytest.mark.db

SNAPSHOT_COLUMNS = {"id", "version", "loaded_at", "source_file", "source_sha256"}

CARD_COLUMNS = {
    "oracle_id",
    "name",  # Card Name, faces joined by " // "
    "face_names",
    "mana_value",
    "type_lines",  # one per face
    "layout",
    "color_identity",
    "produced_mana",
    "commander_legality",
    "oracle_texts",  # one per face
    "keywords",
}

CARD_ARRAY_COLUMNS = {
    "face_names",
    "type_lines",
    "color_identity",
    "produced_mana",
    "oracle_texts",
    "keywords",
}


@pytest.fixture
def inspector(db_engine: Engine) -> Inspector:
    return inspect(db_engine)


def columns_of(inspector: Inspector, table: str) -> dict[str, dict]:
    """The table's columns by name, failing clearly if the table is missing."""
    assert inspector.has_table(table), f"table {table!r} does not exist"
    return {column["name"]: dict(column) for column in inspector.get_columns(table)}


# --- Structure -------------------------------------------------------------


def test_snapshots_table_has_exactly_the_expected_columns(
    inspector: Inspector,
) -> None:
    assert set(columns_of(inspector, "snapshots")) == SNAPSHOT_COLUMNS


def test_cards_table_has_exactly_the_expected_columns(inspector: Inspector) -> None:
    assert set(columns_of(inspector, "cards")) == CARD_COLUMNS


def test_snapshots_are_keyed_by_id(inspector: Inspector) -> None:
    columns_of(inspector, "snapshots")  # the table must exist

    primary_key = inspector.get_pk_constraint("snapshots")["constrained_columns"]

    assert primary_key == ["id"]


def test_cards_are_keyed_by_oracle_id(inspector: Inspector) -> None:
    columns_of(inspector, "cards")  # the table must exist

    primary_key = inspector.get_pk_constraint("cards")["constrained_columns"]

    assert primary_key == ["oracle_id"]


@pytest.mark.parametrize("column", sorted(CARD_ARRAY_COLUMNS))
def test_card_list_columns_are_text_arrays(inspector: Inspector, column: str) -> None:
    column_type = columns_of(inspector, "cards")[column]["type"]

    assert isinstance(column_type, ARRAY), f"{column} is {column_type}, not TEXT[]"
    assert isinstance(column_type.item_type, TEXT), (
        f"{column} is {column_type}, not TEXT[]"
    )


# --- Round trips -----------------------------------------------------------


def test_a_snapshot_row_round_trips(session: Session) -> None:
    loaded_at = datetime(2026, 11, 2, 6, 0, 0, tzinfo=UTC)

    snapshot_id = session.execute(
        text(
            "INSERT INTO snapshots (version, loaded_at, source_file, source_sha256)"
            " VALUES (:version, :loaded_at, :source_file, :source_sha256)"
            " RETURNING id"
        ),
        {
            "version": "20261101220203",
            "loaded_at": loaded_at,
            "source_file": "oracle-cards-20261101220203.jsonl",
            "source_sha256": "ab" * 32,  # a SHA-256 hex digest is 64 characters
        },
    ).scalar_one()

    row = session.execute(
        text("SELECT * FROM snapshots WHERE id = :id"), {"id": snapshot_id}
    ).one()

    assert row.version == "20261101220203"
    assert row.loaded_at == loaded_at
    assert row.source_file == "oracle-cards-20261101220203.jsonl"
    assert row.source_sha256 == "ab" * 32


# Fire // Ice from tests/fixtures/oracle-cards-sample.jsonl: a split card,
# so it has two faces. It has no keywords and produces no mana, which checks
# that empty arrays come back as empty lists.
FIRE_ICE = {
    "oracle_id": "ae92942b-919c-4ea9-b693-85fcef765d5a",
    "name": "Fire // Ice",
    "face_names": ["Fire", "Ice"],
    "mana_value": 4,
    "type_lines": ["Instant", "Instant"],
    "layout": "split",
    "color_identity": ["R", "U"],
    "produced_mana": [],
    "commander_legality": "legal",
    "oracle_texts": [
        "Fire deals 2 damage divided as you choose among one or two targets.",
        "Tap target permanent.\nDraw a card.",
    ],
    "keywords": [],
}


def test_a_card_row_round_trips_with_its_arrays(session: Session) -> None:
    session.execute(
        text(
            "INSERT INTO cards (oracle_id, name, face_names, mana_value, type_lines,"
            " layout, color_identity, produced_mana, commander_legality,"
            " oracle_texts, keywords)"
            " VALUES (:oracle_id, :name, :face_names, :mana_value, :type_lines,"
            " :layout, :color_identity, :produced_mana, :commander_legality,"
            " :oracle_texts, :keywords)"
        ),
        FIRE_ICE,
    )

    row = session.execute(
        text("SELECT * FROM cards WHERE oracle_id = :oracle_id"),
        {"oracle_id": FIRE_ICE["oracle_id"]},
    ).one()

    # str() so the test passes whether oracle_id is stored as UUID or text.
    assert str(row.oracle_id) == FIRE_ICE["oracle_id"]
    assert row.name == "Fire // Ice"
    assert row.face_names == ["Fire", "Ice"]
    assert row.mana_value == 4
    assert row.type_lines == ["Instant", "Instant"]
    assert row.layout == "split"
    assert row.color_identity == ["R", "U"]
    assert row.produced_mana == []
    assert row.commander_legality == "legal"
    assert row.oracle_texts == FIRE_ICE["oracle_texts"]
    assert row.keywords == []
