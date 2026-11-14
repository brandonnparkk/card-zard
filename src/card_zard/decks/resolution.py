"""Match each Deck Line to a Card in the current Snapshot.

For now names must match exactly, character for character. Ignoring case and
accents, Front-Face Names and suggestions come in a later ticket (#5).
Commander lines are matched here and kept apart from the Main Deck. Checking
that they can really lead the deck is #6's job.

Whatever can't be matched to exactly one Card becomes an Unresolved Line and
the rest of the deck still resolves. Nothing is guessed (ADR-0008).
"""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from card_zard.decks.deck_list import (
    DeckLine,
    IgnoredSection,
    ParsedDeckList,
    SectionHeader,
)
from card_zard.snapshots.latest import latest_snapshot
from card_zard.snapshots.models import Card

# Why a line didn't resolve, so the user knows what to fix. A Literal is a
# str at runtime (easy to put in JSON) but pyright rejects any other value.
UnresolvedReason = Literal[
    # The line isn't shaped like `<quantity> <Card Name>` at all.
    "not_a_deck_line",
    # No Card has this exact name.
    "no_matching_card",
    # More than one Card has this exact name. Real data has 15 such names,
    # all Un-set cards like "Everythingamajig" that come in several versions.
    "several_matching_cards",
]


class NoSnapshotError(Exception):
    """No Snapshot has been loaded, so there are no Cards to match against."""


@dataclass(frozen=True)
class ResolvedCard:
    """A Card in the deck, with how many copies the Deck List asked for."""

    oracle_id: UUID
    card_name: str
    quantity: int


@dataclass(frozen=True)
class UnresolvedLine:
    """A line that couldn't be matched to exactly one Card."""

    line_number: int
    # Exactly as the user typed it, to quote back.
    text: str
    reason: UnresolvedReason


@dataclass(frozen=True)
class ResolvedDeck:
    """The result of matching every line of a Deck List against one Snapshot."""

    # The Snapshot the Cards came from, so the answer can say which data it
    # used (ADR-0013).
    snapshot_version: str
    # In the order each Card first appears in the Deck List.
    main_deck: tuple[ResolvedCard, ...]
    # In line order, from the Main Deck and the Commander lines alike.
    unresolved_lines: tuple[UnresolvedLine, ...]
    # From a Commander header or a commander marker. Empty means the Deck
    # List didn't say who leads the deck; it's never guessed.
    commanders: tuple[ResolvedCard, ...] = ()
    # Passed through from parsing, so the user sees what was left out.
    ignored_sections: tuple[IgnoredSection, ...] = ()
    unrecognized_headers: tuple[SectionHeader, ...] = ()


def resolve_deck(session: Session, parsed: ParsedDeckList) -> ResolvedDeck:
    """Match `parsed` against the Cards of the latest Snapshot.

    A Card listed on several lines is merged into one ResolvedCard with the
    quantities added up, separately for the Main Deck and the Commanders.
    Checking Commander's one-copy rule is legality's job (#9), not
    resolution's.

    Raises NoSnapshotError if no Snapshot was ever loaded.
    """
    snapshot = latest_snapshot(session)
    if snapshot is None:
        raise NoSnapshotError("no Snapshot has been loaded yet")

    # One query for every name in the deck, commanders included.
    ids_by_name = _oracle_ids_by_name(
        session,
        {line.card_name for line in parsed.main_deck_lines + parsed.commander_lines},
    )

    unresolved = [
        UnresolvedLine(line.line_number, line.text, "not_a_deck_line")
        for line in parsed.unparsed_lines
    ]
    commanders = _resolve_lines(parsed.commander_lines, ids_by_name, unresolved)
    main_deck = _resolve_lines(parsed.main_deck_lines, ids_by_name, unresolved)

    return ResolvedDeck(
        snapshot_version=snapshot.version,
        main_deck=main_deck,
        # Collected from three places, so sort to put everything back in the
        # order the user typed it.
        unresolved_lines=tuple(sorted(unresolved, key=lambda u: u.line_number)),
        commanders=commanders,
        ignored_sections=parsed.ignored_sections,
        unrecognized_headers=parsed.unrecognized_headers,
    )


def _resolve_lines(
    lines: Iterable[DeckLine],
    ids_by_name: dict[str, list[UUID]],
    unresolved: list[UnresolvedLine],
) -> tuple[ResolvedCard, ...]:
    """Match `lines`, merging repeats; append the failures to `unresolved`."""
    # A plain dict keeps insertion order, so Cards come out in the order each
    # first appears.
    quantities: dict[UUID, int] = {}
    names: dict[UUID, str] = {}

    for line in lines:
        oracle_ids = ids_by_name.get(line.card_name, [])
        if len(oracle_ids) == 1:
            [oracle_id] = oracle_ids
            quantities[oracle_id] = quantities.get(oracle_id, 0) + line.quantity
            names[oracle_id] = line.card_name
        else:
            reason: UnresolvedReason = (
                "no_matching_card" if not oracle_ids else "several_matching_cards"
            )
            unresolved.append(UnresolvedLine(line.line_number, line.text, reason))

    return tuple(
        ResolvedCard(oracle_id, names[oracle_id], quantity)
        for oracle_id, quantity in quantities.items()
    )


def _oracle_ids_by_name(
    session: Session, names: Iterable[str]
) -> dict[str, list[UUID]]:
    """Every Oracle ID with one of these exact names, grouped by name.

    One query for the whole deck rather than one per line. A deck has about
    100 names, so a plain IN (...) is fine here (the loader's 35,000 ids
    needed an array instead).
    """
    names = list(names)
    if not names:
        return {}

    rows = session.execute(
        select(Card.name, Card.oracle_id).where(Card.name.in_(names))
    )
    ids_by_name: defaultdict[str, list[UUID]] = defaultdict(list)
    for name, oracle_id in rows:
        ids_by_name[name].append(oracle_id)
    return ids_by_name
