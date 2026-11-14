"""Tests for matching Deck Lines to Cards in the current Snapshot."""

import json
import uuid
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from card_zard.decks.deck_list import parse_deck_list
from card_zard.decks.resolution import (
    NoSnapshotError,
    ResolvedCard,
    ResolvedDeck,
    UnresolvedLine,
    resolve_deck,
)
from card_zard.snapshots.loader import load_snapshot
from card_zard.snapshots.models import Snapshot

pytestmark = pytest.mark.db

FIXTURE = Path(__file__).parent / "fixtures" / "oracle-cards-sample.jsonl"


@pytest.fixture
def snapshot(session: Session) -> Snapshot:
    """The 65-card fixture Snapshot, loaded into this test's transaction."""
    return load_snapshot(session, FIXTURE)


def oracle_id_of(session: Session, name: str) -> uuid.UUID:
    return session.execute(
        text("SELECT oracle_id FROM cards WHERE name = :name"), {"name": name}
    ).scalar_one()


def resolve(session: Session, deck_list: str) -> ResolvedDeck:
    return resolve_deck(session, parse_deck_list(deck_list))


def write_cards(path: Path, names: list[str]) -> Path:
    """A bulk file with one minimal card per name (names may repeat)."""
    cards: list[dict[str, Any]] = [
        {
            "oracle_id": str(uuid.uuid4()),
            "name": name,
            "layout": "normal",
            "cmc": 1,
            "type_line": "Artifact",
            "color_identity": [],
            "legalities": {"commander": "legal"},
        }
        for name in names
    ]
    path.write_text("".join(json.dumps(c) + "\n" for c in cards), encoding="utf-8")
    return path


# --- Resolving ---


def test_one_sol_ring_resolves_to_the_card_with_quantity_one(
    session: Session, snapshot: Snapshot
) -> None:
    deck = resolve(session, "1 Sol Ring")

    assert deck == ResolvedDeck(
        snapshot_version=snapshot.version,
        main_deck=(
            ResolvedCard(
                oracle_id=oracle_id_of(session, "Sol Ring"),
                card_name="Sol Ring",
                quantity=1,
            ),
        ),
        unresolved_lines=(),
    )


def test_the_main_deck_keeps_the_deck_list_order(
    session: Session, snapshot: Snapshot
) -> None:
    deck = resolve(session, "1 Sol Ring\n1 Command Tower\n1 Arcane Signet")

    assert [card.card_name for card in deck.main_deck] == [
        "Sol Ring",
        "Command Tower",
        "Arcane Signet",
    ]


@pytest.mark.parametrize("name", ["Fire // Ice", "Nazgûl", "Atraxa, Praetors' Voice"])
def test_full_card_names_with_punctuation_and_accents_resolve(
    session: Session, snapshot: Snapshot, name: str
) -> None:
    [card] = resolve(session, f"1 {name}").main_deck

    assert card.card_name == name


def test_a_card_on_several_lines_is_merged_and_quantities_added(
    session: Session, snapshot: Snapshot
) -> None:
    deck = resolve(session, "1 Sol Ring\n10 Plains\n1 Sol Ring\n5 Plains")

    assert [(c.card_name, c.quantity) for c in deck.main_deck] == [
        ("Sol Ring", 2),
        ("Plains", 15),
    ]


def test_the_result_names_the_latest_snapshot(
    session: Session, snapshot: Snapshot, tmp_path: Path
) -> None:
    newer = load_snapshot(session, write_cards(tmp_path / "newer.jsonl", ["Sol Ring"]))

    deck = resolve(session, "1 Sol Ring")

    assert newer.id != snapshot.id
    assert deck.snapshot_version == newer.version


# --- Unresolved Lines ---


def test_an_unknown_name_is_unresolved_and_the_rest_still_resolves(
    session: Session, snapshot: Snapshot
) -> None:
    deck = resolve(session, "1 Sol Ring\n1 Sol Rnig\n1 Arcane Signet")

    assert [card.card_name for card in deck.main_deck] == ["Sol Ring", "Arcane Signet"]
    assert deck.unresolved_lines == (
        UnresolvedLine(line_number=2, text="1 Sol Rnig", reason="no_matching_card"),
    )


@pytest.mark.parametrize(
    "line",
    [
        "1 sol ring",  # case: issue #5
        "1 Nazgul",  # accents: issue #5
        "1 Fire",  # Front-Face Name: issue #5
    ],
)
def test_names_must_match_exactly_for_now(
    session: Session, snapshot: Snapshot, line: str
) -> None:
    deck = resolve(session, line)

    assert deck.main_deck == ()
    assert [u.reason for u in deck.unresolved_lines] == ["no_matching_card"]


def test_a_name_shared_by_several_cards_is_not_guessed(
    session: Session, tmp_path: Path
) -> None:
    """Real Un-set cards like Everythingamajig share one name across versions."""
    load_snapshot(
        session,
        write_cards(tmp_path / "cards.jsonl", ["Everythingamajig"] * 2 + ["Sol Ring"]),
    )

    deck = resolve(session, "1 Everythingamajig\n1 Sol Ring")

    assert [card.card_name for card in deck.main_deck] == ["Sol Ring"]
    assert deck.unresolved_lines == (
        UnresolvedLine(
            line_number=1, text="1 Everythingamajig", reason="several_matching_cards"
        ),
    )


def test_lines_that_are_not_deck_lines_are_unresolved_in_line_order(
    session: Session, snapshot: Snapshot
) -> None:
    deck = resolve(session, "1 Sol Rnig\n0 Sol Ring\n1 Sol Ring\n0 Arcane Signet")

    assert deck.unresolved_lines == (
        UnresolvedLine(line_number=1, text="1 Sol Rnig", reason="no_matching_card"),
        UnresolvedLine(line_number=2, text="0 Sol Ring", reason="not_a_deck_line"),
        UnresolvedLine(line_number=4, text="0 Arcane Signet", reason="not_a_deck_line"),
    )


def test_an_empty_deck_list_resolves_to_an_empty_deck(
    session: Session, snapshot: Snapshot
) -> None:
    deck = resolve(session, "")

    assert deck.main_deck == ()
    assert deck.unresolved_lines == ()
    assert deck.snapshot_version == snapshot.version


# --- No Snapshot ---


def test_resolving_before_any_snapshot_is_loaded_is_an_error(session: Session) -> None:
    with pytest.raises(NoSnapshotError):
        resolve(session, "1 Sol Ring")
