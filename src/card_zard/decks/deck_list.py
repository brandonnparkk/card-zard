"""Split a pasted Deck List into Deck Lines.

This module only reads text; it knows nothing about Cards or the database.
Matching each Deck Line to a Card happens later, in resolution, so the parsing
rules here can be tested on their own.

For now a Deck Line is exactly `<quantity> <Card Name>`, such as `1 Sol Ring`.
Set codes, `1x`, lines without a quantity and section headers come in a later
ticket (#4). Until then those lines aren't guessed at: they come back as
UnparsedLines, so they can be reported to the user (ADR-0008).
"""

import re
from dataclasses import dataclass

# A quantity, whitespace, then the Card Name (everything up to the end).
# [0-9] rather than \d: \d also matches digits from other scripts, such as
# "٣", which int() would happily turn into 3.
_DECK_LINE = re.compile(r"(?P<quantity>[0-9]+)\s+(?P<card_name>.+)")


@dataclass(frozen=True)
class DeckLine:
    """One line of a Deck List naming a quantity and a card."""

    # 1-based, so it matches what the user sees in their text box.
    line_number: int
    quantity: int
    # As typed, minus surrounding whitespace. Not checked against real Cards;
    # a misspelled name is still a Deck Line until resolution fails to match it.
    card_name: str
    # The whole line exactly as typed, so a report can quote it back.
    text: str


@dataclass(frozen=True)
class UnparsedLine:
    """A non-blank line that isn't shaped like a Deck Line."""

    line_number: int
    text: str


@dataclass(frozen=True)
class ParsedDeckList:
    """Every non-blank line of a Deck List, sorted into the two kinds.

    Tuples rather than lists, so a frozen ParsedDeckList really can't change.
    Both keep the order of the original text.
    """

    deck_lines: tuple[DeckLine, ...]
    unparsed_lines: tuple[UnparsedLine, ...]


def parse_deck_list(text: str) -> ParsedDeckList:
    """Sort every non-blank line of `text` into a DeckLine or an UnparsedLine.

    Blank lines (including ones that are only spaces) are skipped. Nothing
    else is ever dropped. Repeated cards are not merged either: `1 Sol Ring`
    twice gives two DeckLines, and it's resolution's job to notice.
    """
    deck_lines: list[DeckLine] = []
    unparsed_lines: list[UnparsedLine] = []

    # splitlines() handles \n, \r\n (Windows) and \r line endings alike.
    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue

        deck_line = _parse_line(line_number, line, stripped)
        if deck_line is None:
            unparsed_lines.append(UnparsedLine(line_number=line_number, text=line))
        else:
            deck_lines.append(deck_line)

    return ParsedDeckList(
        deck_lines=tuple(deck_lines), unparsed_lines=tuple(unparsed_lines)
    )


def _parse_line(line_number: int, line: str, stripped: str) -> DeckLine | None:
    """The DeckLine for one non-blank line, or None if it isn't one."""
    # fullmatch, not match: the pattern must cover the whole line, so a stray
    # character can't hide at the end.
    match = _DECK_LINE.fullmatch(stripped)
    if match is None:
        return None

    quantity = int(match["quantity"])
    # "0 Sol Ring" is shaped right but means nothing in a deck. Treat it as
    # unparsed instead of guessing whether the user meant 1 or a removal.
    if quantity == 0:
        return None

    return DeckLine(
        line_number=line_number,
        quantity=quantity,
        # No .strip() needed: the line was stripped, and the greedy \s+ in the
        # pattern already took every space between the quantity and the name.
        card_name=match["card_name"],
        text=line,
    )
