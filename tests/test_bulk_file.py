"""Tests for reading a Scryfall bulk file into Card rows (no database needed)."""

import json
import uuid
from pathlib import Path
from typing import Any

import pytest

from card_zard.snapshots.bulk_file import (
    NON_GAME_LAYOUTS,
    is_game_card,
    read_card_rows,
    to_card_row,
)

FIXTURE = Path(__file__).parent / "fixtures" / "oracle-cards-sample.jsonl"


def make_record(**fields: Any) -> dict[str, Any]:
    """A minimal Scryfall card object with only the fields the reader uses."""
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
    return record


def write_lines(path: Path, lines: list[str]) -> Path:
    path.write_text("".join(line + "\n" for line in lines), encoding="utf-8")
    return path


def write_records(path: Path, records: list[dict[str, Any]]) -> Path:
    return write_lines(path, [json.dumps(r, ensure_ascii=False) for r in records])


# --- read_card_rows: the whole file ---


def test_fixture_yields_one_row_per_game_card() -> None:
    rows = list(read_card_rows(FIXTURE))

    # Same count test_load_snapshot.py expects in the database: 75 lines
    # minus 10 in non-game layouts.
    assert len(rows) == 65
    assert len({row["oracle_id"] for row in rows}) == 65


def test_fixture_rows_use_only_game_layouts() -> None:
    layouts = {row["layout"] for row in read_card_rows(FIXTURE)}

    assert layouts.isdisjoint(NON_GAME_LAYOUTS)


def test_blank_lines_are_ignored(tmp_path: Path) -> None:
    line = json.dumps(make_record())
    path = write_lines(tmp_path / "cards.jsonl", ["", line, "   ", ""])

    assert len(list(read_card_rows(path))) == 1


def test_non_ascii_names_survive(tmp_path: Path) -> None:
    path = write_records(tmp_path / "cards.jsonl", [make_record(name="Nazgûl")])

    assert [row["name"] for row in read_card_rows(path)] == ["Nazgûl"]


def test_invalid_json_raises_value_error_naming_the_line(tmp_path: Path) -> None:
    good = json.dumps(make_record())
    path = write_lines(tmp_path / "bad.jsonl", [good, '{"oracle_id": "not finished'])

    with pytest.raises(ValueError, match=r"bad\.jsonl line 2"):
        list(read_card_rows(path))


def test_a_line_that_is_not_an_object_raises_value_error(tmp_path: Path) -> None:
    path = write_lines(tmp_path / "bad.jsonl", ["[1, 2, 3]"])

    with pytest.raises(ValueError, match="line 1: expected a JSON object"):
        list(read_card_rows(path))


def test_a_record_missing_a_required_field_names_the_card(tmp_path: Path) -> None:
    record = make_record(name="Broken Card")
    del record["cmc"]
    path = write_records(tmp_path / "bad.jsonl", [record])

    with pytest.raises(ValueError, match=r"line 1: can't read card 'Broken Card'"):
        list(read_card_rows(path))


def test_rows_are_read_lazily(tmp_path: Path) -> None:
    """A bad line late in the file isn't reached until iteration gets there."""
    good = json.dumps(make_record())
    path = write_lines(tmp_path / "cards.jsonl", [good, "not json"])

    rows = read_card_rows(path)
    first = next(rows)

    assert first["name"] == "Test Card"
    with pytest.raises(ValueError, match="line 2"):
        next(rows)


# --- is_game_card ---


@pytest.mark.parametrize("layout", sorted(NON_GAME_LAYOUTS))
def test_non_game_layouts_are_skipped(layout: str) -> None:
    assert not is_game_card(make_record(layout=layout))


@pytest.mark.parametrize(
    "layout", ["normal", "split", "adventure", "modal_dfc", "meld", "saga"]
)
def test_game_layouts_are_kept(layout: str) -> None:
    assert is_game_card(make_record(layout=layout))


def test_unknown_future_layouts_are_kept() -> None:
    assert is_game_card(make_record(layout="some_layout_scryfall_adds_later"))


# --- to_card_row: mapping one record ---


def test_single_faced_card_becomes_one_face() -> None:
    record = make_record(
        name="Birds of Paradise",
        cmc=1,
        type_line="Creature — Bird",
        oracle_text="Flying\n{T}: Add one mana of any color.",
        color_identity=["G"],
        produced_mana=["B", "G", "R", "U", "W"],
        keywords=["Flying"],
    )

    row = to_card_row(record)

    assert row == {
        "oracle_id": uuid.UUID(record["oracle_id"]),
        "name": "Birds of Paradise",
        "mana_value": 1.0,
        "layout": "normal",
        "commander_legality": "legal",
        "face_names": ["Birds of Paradise"],
        "type_lines": ["Creature — Bird"],
        "oracle_texts": ["Flying\n{T}: Add one mana of any color."],
        "color_identity": ["G"],
        "produced_mana": ["B", "G", "R", "U", "W"],
        "keywords": ["Flying"],
    }


def test_multi_faced_card_takes_face_fields_from_card_faces() -> None:
    record = make_record(
        name="Fire // Ice",
        layout="split",
        type_line="Instant // Instant",
        card_faces=[
            {"name": "Fire", "type_line": "Instant", "oracle_text": "Fire text."},
            {"name": "Ice", "type_line": "Instant", "oracle_text": "Ice text."},
        ],
    )
    del record["oracle_text"]

    row = to_card_row(record)

    assert row["name"] == "Fire // Ice"
    assert row["face_names"] == ["Fire", "Ice"]
    assert row["type_lines"] == ["Instant", "Instant"]
    assert row["oracle_texts"] == ["Fire text.", "Ice text."]


def test_oracle_id_is_a_uuid_object() -> None:
    record = make_record()

    assert to_card_row(record)["oracle_id"] == uuid.UUID(record["oracle_id"])


def test_oracle_id_falls_back_to_the_first_face() -> None:
    """Reversible cards carry oracle_id on their faces, not the top level."""
    face_id = str(uuid.uuid4())
    face = {"name": "Side", "type_line": "Creature", "oracle_id": face_id}
    record = make_record(layout="reversible_card", card_faces=[face, face])
    del record["oracle_id"]

    assert to_card_row(record)["oracle_id"] == uuid.UUID(face_id)


def test_a_card_with_no_oracle_id_anywhere_is_an_error() -> None:
    record = make_record()
    del record["oracle_id"]

    with pytest.raises(ValueError, match="no oracle_id"):
        to_card_row(record)


def test_missing_optional_fields_become_empty() -> None:
    record = make_record()
    del record["keywords"]
    del record["oracle_text"]

    row = to_card_row(record)

    assert row["produced_mana"] == []
    assert row["keywords"] == []
    assert row["oracle_texts"] == [""]


def test_half_mana_values_are_kept() -> None:
    assert to_card_row(make_record(cmc=0.5))["mana_value"] == 0.5
