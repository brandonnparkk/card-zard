"""Loading a Scryfall bulk file into a Snapshot and Cards (issue #2, ADR-0013).

Most tests write a small JSONL file of hand-written cards to `tmp_path`, load
it, and read the rows back with plain SQL, so they don't depend on how the
models are written.

The agreed interface is `load_snapshot(session, path) -> Snapshot` in
`card_zard.snapshots.loader`. It never commits: a real caller wraps it in
`with session.begin():`, and the `load` helper below does the same.
"""

import hashlib
import json
import re
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Row, text
from sqlalchemy.orm import Session

pytestmark = pytest.mark.db

FIXTURE = Path(__file__).parent / "fixtures" / "oracle-cards-sample.jsonl"

# Counted once from FIXTURE: 75 lines, minus the 10 in skipped layouts
# (2 art_series, 2 token, and 1 each of double_faced_token, emblem,
# front_card, planar, scheme and vanguard). Every one of the 65 left has its
# own oracle_id.
FIXTURE_CARD_COUNT = 65

SKIPPED_LAYOUTS = [
    "art_series",
    "token",
    "double_faced_token",
    "emblem",
    "front_card",
    "planar",
    "scheme",
    "vanguard",
]


# --- Helpers ---------------------------------------------------------------


def load_snapshot(session: Session, path: Path):
    """Call the loader under test, without wrapping it in a transaction.

    The import is in here rather than at the top of the file so that, until
    the loader exists, each test fails on its own instead of the whole test
    run failing to collect.
    """
    from card_zard.snapshots.loader import (  # pyright: ignore[reportMissingImports]
        load_snapshot as loader,
    )

    return loader(session, path)


def load(session: Session, path: Path):
    """Load `path` the way a real caller does, in its own transaction."""
    with session.begin():
        snapshot = load_snapshot(session, path)
    return snapshot


def make_card(**fields: Any) -> dict[str, Any]:
    """A minimal single-faced card in Scryfall's shape.

    It has only the fields the loader reads. Pass keyword arguments to
    override or add fields. `produced_mana` is left out, as it is for most
    real cards that don't make mana.
    """
    card: dict[str, Any] = {
        "oracle_id": str(uuid.uuid4()),
        "name": "Test Card",
        "layout": "normal",
        "cmc": 2.0,
        "type_line": "Creature — Human",
        "oracle_text": "Vigilance",
        "color_identity": ["W"],
        "keywords": ["Vigilance"],
        "legalities": {"commander": "legal"},
    }
    card.update(fields)
    return card


def write_cards(path: Path, cards: list[dict[str, Any]]) -> Path:
    """Write `cards` as a JSONL bulk file, one card per line, and return path."""
    lines = (json.dumps(card, ensure_ascii=False) + "\n" for card in cards)
    path.write_text("".join(lines), encoding="utf-8")
    return path


def cards_by_oracle_id(session: Session) -> dict[str, Row[Any]]:
    """Every row in `cards`, keyed by oracle_id as a string.

    str() so this works whether oracle_id is stored as UUID or text.
    """
    rows = session.execute(text("SELECT * FROM cards")).all()
    return {str(row.oracle_id): row for row in rows}


def snapshot_rows(session: Session) -> list[Row[Any]]:
    return list(session.execute(text("SELECT * FROM snapshots ORDER BY id")).all())


def count_rows(session: Session, table: str) -> int:
    return session.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()


# --- The fixture set -------------------------------------------------------


def test_loading_the_fixture_set_loads_every_game_card(session: Session) -> None:
    load(session, FIXTURE)

    assert count_rows(session, "cards") == FIXTURE_CARD_COUNT


def test_fixture_cards_can_be_read_back_by_oracle_id(session: Session) -> None:
    """Spot checks on edge cases: a split card, a ban, an accent, a name clash."""
    by_name_and_layout = {
        (card["name"], card["layout"]): card["oracle_id"]
        for card in map(json.loads, FIXTURE.read_text(encoding="utf-8").splitlines())
    }
    load(session, FIXTURE)
    cards = cards_by_oracle_id(session)

    fire_ice = cards[by_name_and_layout[("Fire // Ice", "split")]]
    assert fire_ice.face_names == ["Fire", "Ice"]
    assert cards[by_name_and_layout[("Black Lotus", "normal")]].commander_legality == (
        "banned"
    )
    assert cards[by_name_and_layout[("Nazgûl", "normal")]].name == "Nazgûl"
    # The art series "Sol Ring // Sol Ring" has its own oracle_id and is skipped.
    assert by_name_and_layout[("Sol Ring", "normal")] in cards
    assert by_name_and_layout[("Sol Ring // Sol Ring", "art_series")] not in cards


# --- Column mapping --------------------------------------------------------


def test_single_faced_card_maps_to_every_column(
    session: Session, tmp_path: Path
) -> None:
    """A card without card_faces has one face, named after the card."""
    birds = make_card(
        name="Birds of Paradise",
        cmc=1.0,
        type_line="Creature — Bird",
        oracle_text="Flying\n{T}: Add one mana of any color.",
        color_identity=["G"],
        produced_mana=["B", "G", "R", "U", "W"],
        keywords=["Flying"],
    )
    load(session, write_cards(tmp_path / "cards.jsonl", [birds]))

    row = cards_by_oracle_id(session)[birds["oracle_id"]]

    assert row.name == "Birds of Paradise"
    assert row.face_names == ["Birds of Paradise"]
    assert row.mana_value == 1
    assert row.type_lines == ["Creature — Bird"]
    assert row.layout == "normal"
    assert row.color_identity == ["G"]
    assert row.produced_mana == ["B", "G", "R", "U", "W"]
    assert row.commander_legality == "legal"
    assert row.oracle_texts == ["Flying\n{T}: Add one mana of any color."]
    assert row.keywords == ["Flying"]


def test_multi_faced_card_takes_face_fields_from_card_faces(
    session: Session, tmp_path: Path
) -> None:
    """Face names, type lines and oracle texts come from each card_faces entry.

    Like real adventure cards, this one has no top-level oracle_text.
    """
    bonecrusher = make_card(
        name="Bonecrusher Giant // Stomp",
        layout="adventure",
        cmc=3.0,
        type_line="Creature — Giant // Instant — Adventure",
        color_identity=["R"],
        keywords=[],
        card_faces=[
            {
                "name": "Bonecrusher Giant",
                "type_line": "Creature — Giant",
                "oracle_text": "Whenever this creature becomes the target of a"
                " spell, this creature deals 2 damage to that spell's controller.",
            },
            {
                "name": "Stomp",
                "type_line": "Instant — Adventure",
                "oracle_text": "Damage can't be prevented this turn."
                " Stomp deals 2 damage to any target.",
            },
        ],
    )
    del bonecrusher["oracle_text"]
    load(session, write_cards(tmp_path / "cards.jsonl", [bonecrusher]))

    row = cards_by_oracle_id(session)[bonecrusher["oracle_id"]]

    assert row.name == "Bonecrusher Giant // Stomp"
    assert row.face_names == ["Bonecrusher Giant", "Stomp"]
    assert row.type_lines == ["Creature — Giant", "Instant — Adventure"]
    assert row.oracle_texts == [
        face["oracle_text"] for face in bonecrusher["card_faces"]
    ]
    assert row.layout == "adventure"
    assert row.mana_value == 3


def test_missing_produced_mana_and_keywords_become_empty_arrays(
    session: Session, tmp_path: Path
) -> None:
    card = make_card()
    del card["keywords"]
    assert "produced_mana" not in card
    load(session, write_cards(tmp_path / "cards.jsonl", [card]))

    row = cards_by_oracle_id(session)[card["oracle_id"]]

    assert row.produced_mana == []
    assert row.keywords == []


@pytest.mark.parametrize("layout", SKIPPED_LAYOUTS)
def test_non_game_layouts_are_not_loaded(
    session: Session, tmp_path: Path, layout: str
) -> None:
    """Tokens, emblems, art series and the like aren't Cards in a deck."""
    game_card = make_card(name="Real Card")
    non_game_card = make_card(name="Not A Card", layout=layout)
    load(session, write_cards(tmp_path / "cards.jsonl", [game_card, non_game_card]))

    assert set(cards_by_oracle_id(session)) == {game_card["oracle_id"]}


# --- The Snapshot row ------------------------------------------------------


def test_load_records_a_snapshot_and_returns_it(
    session: Session, tmp_path: Path
) -> None:
    """version is the load time in UTC, like "2026-11-07T06:00:00Z".

    The time checks allow a minute either way, in case the database
    container's clock differs a little from this machine's.
    """
    path = write_cards(tmp_path / "oracle-cards-test.jsonl", [make_card()])
    before = datetime.now(UTC)
    snapshot = load(session, path)
    after = datetime.now(UTC)

    [row] = snapshot_rows(session)

    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(\.\d+)?Z", row.version)
    version_time = datetime.fromisoformat(row.version)
    slack = timedelta(minutes=1)
    assert before - slack <= version_time <= after + slack
    assert before - slack <= row.loaded_at <= after + slack
    assert row.source_file == "oracle-cards-test.jsonl"
    assert row.source_sha256 == hashlib.sha256(path.read_bytes()).hexdigest()

    assert snapshot.id == row.id
    assert snapshot.version == row.version
    assert snapshot.source_file == row.source_file
    assert snapshot.source_sha256 == row.source_sha256


# --- Loading again ---------------------------------------------------------


def test_reloading_a_changed_card_updates_its_row_in_place(
    session: Session, tmp_path: Path
) -> None:
    """Cards are upserted by oracle_id, not copied per Snapshot (ADR-0013)."""
    old = make_card(name="Old Name", oracle_text="Old text.")
    new = {**old, "name": "New Name", "oracle_text": "New text."}
    load(session, write_cards(tmp_path / "first.jsonl", [old]))
    load(session, write_cards(tmp_path / "second.jsonl", [new]))

    cards = cards_by_oracle_id(session)

    assert list(cards) == [old["oracle_id"]]
    assert cards[old["oracle_id"]].name == "New Name"
    assert cards[old["oracle_id"]].oracle_texts == ["New text."]
    assert count_rows(session, "snapshots") == 2


def test_reloading_deletes_cards_missing_from_the_new_file(
    session: Session, tmp_path: Path
) -> None:
    kept = make_card(name="Kept")
    dropped = make_card(name="Dropped")
    load(session, write_cards(tmp_path / "first.jsonl", [kept, dropped]))
    load(session, write_cards(tmp_path / "second.jsonl", [kept]))

    assert set(cards_by_oracle_id(session)) == {kept["oracle_id"]}


def test_reloading_the_same_file_returns_the_existing_snapshot(
    session: Session, tmp_path: Path
) -> None:
    """The check is on the file's hash, so a renamed copy counts as the same."""
    cards = [make_card()]
    first = load(session, write_cards(tmp_path / "first.jsonl", cards))
    again = load(session, write_cards(tmp_path / "copy.jsonl", cards))

    assert again.id == first.id
    assert count_rows(session, "snapshots") == 1


def test_a_failed_load_leaves_earlier_cards_and_snapshots_unchanged(
    session: Session, tmp_path: Path
) -> None:
    """A malformed line partway through undoes everything this load did.

    The bad file changes a card and adds one before the malformed line, so a
    half-applied load would show up. The load runs in a savepoint, which is
    rolled back when the exception leaves the `with` block.
    """
    original = make_card(name="Original")
    load(session, write_cards(tmp_path / "good.jsonl", [original]))

    bad = tmp_path / "bad.jsonl"
    write_cards(bad, [{**original, "name": "Changed"}, make_card(name="Added")])
    with bad.open("a", encoding="utf-8") as file:
        file.write('{"oracle_id": "not finished\n')

    # json.loads raises json.JSONDecodeError, which is a ValueError.
    with pytest.raises(ValueError):
        with session.begin_nested():
            load_snapshot(session, bad)

    cards = cards_by_oracle_id(session)
    assert list(cards) == [original["oracle_id"]]
    assert cards[original["oracle_id"]].name == "Original"
    assert count_rows(session, "snapshots") == 1


# --- Transactions ----------------------------------------------------------


def test_load_snapshot_leaves_committing_to_the_caller(
    session: Session, tmp_path: Path
) -> None:
    """Rolling back after load_snapshot undoes the whole load.

    In these tests a commit only releases a savepoint (see conftest.py), so if
    load_snapshot committed, its rows would survive the rollback below.
    """
    load_snapshot(session, write_cards(tmp_path / "cards.jsonl", [make_card()]))

    assert session.in_transaction(), "load_snapshot ended the session's transaction"
    session.rollback()
    assert count_rows(session, "cards") == 0
    assert count_rows(session, "snapshots") == 0
