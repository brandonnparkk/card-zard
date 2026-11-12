"""Read a Scryfall Oracle Cards bulk file and turn its records into Card rows.

This module only reads and reshapes data; it never touches the database. The
loader (phase 2) takes the rows `read_card_rows` yields and upserts them, so
the parsing rules here can be tested without Postgres.

The bulk file is JSON Lines: one Scryfall card object per line.
"""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any, TypedDict
from uuid import UUID

# Layouts that are never a Card in a deck: tokens, emblems, art-series cards
# and the oversized Planechase, Archenemy and Vanguard cards. Everything else
# is loaded, including layouts Scryfall adds later. That's deliberate: a new
# game layout appearing as a Card is a smaller mistake than it silently
# disappearing from every deck that uses it (ADR-0008).
NON_GAME_LAYOUTS = frozenset(
    {
        "art_series",
        "token",
        "double_faced_token",
        "emblem",
        "front_card",
        "planar",
        "scheme",
        "vanguard",
    }
)


class CardRow(TypedDict):
    """One row for the `cards` table, keyed by the Card model's column names.

    A TypedDict is a plain dict at runtime, so the loader can hand a list of
    these straight to an INSERT, while pyright still checks every key and type.
    """

    oracle_id: UUID
    name: str
    mana_value: float
    layout: str
    commander_legality: str
    face_names: list[str]
    type_lines: list[str]
    oracle_texts: list[str]
    color_identity: list[str]
    produced_mana: list[str]
    keywords: list[str]


def read_card_rows(path: Path) -> Iterator[CardRow]:
    """Yield a CardRow for every game card in the bulk file at `path`.

    This is a generator, so the file is read one line at a time and the whole
    ~200 MB file never sits in memory at once. Nothing happens until the
    caller starts iterating.

    Raises ValueError, naming the line, if a line isn't a JSON object or a
    record is missing a field every card must have.
    """
    for line_number, record in _read_records(path):
        try:
            if not is_game_card(record):
                continue
            row = to_card_row(record)
        except (KeyError, TypeError, ValueError) as error:
            # Re-raise as one exception type with the location attached. The
            # bare KeyError would just say 'cmc', with no hint which card.
            raise ValueError(
                f"{path.name} line {line_number}: can't read card "
                f"{record.get('name', '<no name>')!r}: {error!r}"
            ) from error
        # Yield outside the try, so only errors from reading this record get
        # the "can't read card" wrapper, not anything else that happens while
        # the generator is paused at the yield.
        yield row


def is_game_card(record: dict[str, Any]) -> bool:
    """Whether a Scryfall record is a card you could put in a deck."""
    return record["layout"] not in NON_GAME_LAYOUTS


def to_card_row(record: dict[str, Any]) -> CardRow:
    """Map one Scryfall card object onto the `cards` table's columns.

    Multi-faced cards (split, adventure, modal DFC, transform, flip...) keep
    each face's name, type line and rules text in `card_faces`. Single-faced
    cards have none, so we treat the record itself as the only face. Either
    way every per-face column gets one entry per face, in Scryfall's order.
    """
    faces: list[dict[str, Any]] = record.get("card_faces") or [record]

    return {
        "oracle_id": _oracle_id(record, faces),
        # Always the full name, e.g. "Fire // Ice". face_names holds the parts.
        "name": record["name"],
        # Scryfall calls it cmc. float() because JSON may give 3 instead of 3.0.
        "mana_value": float(record["cmc"]),
        "layout": record["layout"],
        "commander_legality": record["legalities"]["commander"],
        "face_names": [face["name"] for face in faces],
        "type_lines": [face["type_line"] for face in faces],
        # Vanilla creatures have no rules text. Scryfall usually sends "" but
        # can omit the key, and both should mean "no text", not an error.
        "oracle_texts": [face.get("oracle_text", "") for face in faces],
        "color_identity": record["color_identity"],
        # Scryfall omits produced_mana for cards that make no mana, and
        # keywords is optional in its schema. The columns are NOT NULL arrays,
        # so a missing field becomes [].
        "produced_mana": record.get("produced_mana", []),
        "keywords": record.get("keywords", []),
    }


def _oracle_id(record: dict[str, Any], faces: list[dict[str, Any]]) -> UUID:
    """The record's Oracle ID as a UUID object (the column is native uuid).

    Reversible cards are the one layout where Scryfall puts oracle_id on each
    face instead of the top level, so fall back to the first face.
    """
    value = record.get("oracle_id") or faces[0].get("oracle_id")
    if value is None:
        raise ValueError("record has no oracle_id")
    return UUID(value)


def _read_records(path: Path) -> Iterator[tuple[int, dict[str, Any]]]:
    """Yield (line number, parsed object) for each non-blank line."""
    # Explicit utf-8: on Windows the default encoding isn't UTF-8, and names
    # like "Nazgûl" would be misread.
    with path.open(encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"{path.name} line {line_number}: invalid JSON: {error.msg}"
                ) from error
            if not isinstance(record, dict):
                raise ValueError(
                    f"{path.name} line {line_number}: expected a JSON object"
                )
            yield line_number, record
