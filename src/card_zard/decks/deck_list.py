"""Split a pasted Deck List into Deck Lines.

This module only reads text; it knows nothing about Cards or the database.
Matching each Deck Line to a Card happens later, in resolution, so the parsing
rules here can be tested on their own.

A Deck Line is a quantity and a card, written the way deck sites export it:

    1 Sol Ring
    1x Sol Ring
    1 Sol Ring (C21) 263 *F*
    1x Baba Lysaga, Night Witch (clb) 525 *E* [Commander{top}] ^Have,#37d67a^

The printing (set code and collector number), finish markers and tags are
dropped, because Card Zard identifies Cards by Oracle ID (ADR-0006). The
markers that change where a card belongs are kept: "this is the commander",
"this is the companion" and Archidekt's "not in the deck" flag.

Section headers (`Commander`, `Sideboard:`, `//Maybeboard`, ...) decide where
the lines under them belong: the Main Deck, the Commander, or an Ignored
Section that is listed back to the user but not analyzed. A commander is only
ever found from an explicit header or marker, never from where a line sits
(ADR-0008).

Whatever can't be read is kept as an UnparsedLine, so it is reported rather
than guessed at.
"""

import re
from dataclasses import dataclass
from typing import Literal

# A quantity, an optional x (Archidekt and TappedOut write "1x"), whitespace,
# then the rest of the line. [0-9] rather than \d: \d also matches digits from
# other scripts, such as "٣", which int() would happily turn into 3.
_QUANTITY = re.compile(r"(?P<quantity>[0-9]+)[xX]?\s+(?P<rest>.+)")

# Where the name ends and the trailing markers and tags begin: *, [, ^ or #,
# after whitespace or at the very start (then there's no name at all). No real
# Card Name contains any of those four characters (checked against all 35,011
# names), so this can't cut a name.
_MARKERS_START = re.compile(r"(?:^|\s+)(?=[*\[^#])")

# The markers and tags that may follow a name. The whole tail must be made of
# these, so unexpected text after a name makes the line unparsed instead of
# being quietly thrown away.
#   *F*  *E*  *F:pre*  *CMDR*  *CMPN*   finishes and TappedOut markers
#   [Commander{top}]  [Ramp,Draw]       Archidekt categories
#   ^Have,#37d67a^                      Archidekt colour tags
#   #interaction  #!free spell          Moxfield tags (always last)
_MARKER_TOKEN = r"\*[^*\s]+\*|\[[^\]]*\]|\^[^^]*\^|#.*"
_MARKERS = re.compile(rf"(?:\s*(?:{_MARKER_TOKEN}))+\s*")

# The printing at the end of the name: a set code in parentheses, then an
# optional collector number. The set code must be all uppercase (Moxfield,
# Arena), all lowercase (Archidekt) or empty (Archidekt's Arena export), with
# an optional ":<number>" (TappedOut). Mixed case is NOT a set code: the real
# card "Hazmat Suit (Used)" must keep its "(Used)".
# Collector numbers come as 263, 1492★, 82s, E01-54 or 2023-8: any one token.
# It may also start the text, in "(C21) 263" with no name: then nothing is
# left and the line is rejected.
_PRINTING = re.compile(r"(?:^|\s+)\((?:[A-Z0-9]*|[a-z0-9]*)(?::[0-9]+)?\)(?:\s+\S+)?$")

# Where a marked card belongs, when a marker says so.
LineMarker = Literal[
    # TappedOut *CMDR*, or an Archidekt [Commander] category.
    "commander",
    # TappedOut *CMPN*. A Companion starts outside the game, not in the deck.
    "companion",
    # Archidekt's {noDeck} flag, which it puts on maybeboard cards.
    "maybeboard",
]


@dataclass(frozen=True)
class DeckLine:
    """One line of a Deck List naming a quantity and a card."""

    # 1-based, so it matches what the user sees in their text box.
    line_number: int
    quantity: int
    # Just the name: no quantity, printing, markers or surrounding whitespace.
    # Not checked against real Cards; a misspelled name is still a Deck Line
    # until resolution fails to match it.
    card_name: str
    # The whole line exactly as typed, so a report can quote it back.
    text: str
    # Set only when the line itself says where the card belongs.
    marker: LineMarker | None = None


@dataclass(frozen=True)
class UnparsedLine:
    """A non-blank line that isn't shaped like a Deck Line."""

    line_number: int
    text: str


@dataclass(frozen=True)
class IgnoredLine:
    """A line in an Ignored Section, kept exactly as typed."""

    line_number: int
    text: str


@dataclass(frozen=True)
class IgnoredSection:
    """A part of the Deck List that isn't part of the deck, like a Sideboard."""

    # A tidy name, such as "Sideboard", whatever the header looked like.
    name: str
    lines: tuple[IgnoredLine, ...]


@dataclass(frozen=True)
class SectionHeader:
    """A header line that isn't one of the known section names.

    Deck sites export their own groupings as headers, such as Archidekt's
    categories ("Ramp") or card types ("Creature"). Their cards stay in the
    Main Deck, and the headers are listed back so nothing is hidden.
    """

    line_number: int
    text: str
    # The header without decoration: "//Draw / Advantage" becomes
    # "Draw / Advantage", and "Creatures (30)" becomes "Creatures".
    name: str


@dataclass(frozen=True)
class ParsedDeckList:
    """Every non-blank line of a Deck List, sorted by where it belongs.

    Tuples rather than lists, so a frozen ParsedDeckList really can't change.
    Each keeps the order of the original text.
    """

    main_deck_lines: tuple[DeckLine, ...]
    # Under a Commander header, or marked as the commander.
    commander_lines: tuple[DeckLine, ...] = ()
    ignored_sections: tuple[IgnoredSection, ...] = ()
    unrecognized_headers: tuple[SectionHeader, ...] = ()
    # Empty tuples are safe defaults: unlike lists, they can't be changed.
    unparsed_lines: tuple[UnparsedLine, ...] = ()


@dataclass(frozen=True)
class CardText:
    """What's left of a line once its quantity is taken off."""

    card_name: str
    marker: LineMarker | None


def parse_deck_list(text: str) -> ParsedDeckList:
    """Sort every non-blank line of `text` by where it belongs.

    Blank lines (including ones that are only spaces) are skipped, and they
    don't end a section: deck sites put blank lines in odd places. Nothing
    else is ever dropped. Repeated cards are not merged either: `1 Sol Ring`
    twice gives two DeckLines, and it's resolution's job to notice.
    """
    # splitlines() handles \n, \r\n (Windows) and \r line endings alike.
    lines = [
        (line_number, line, line.strip())
        for line_number, line in enumerate(text.splitlines(), start=1)
        if line.strip()
    ]

    # Decided once, for the whole list. If any card line has a quantity, the
    # list came from a deck site, and a line without one is a header such as
    # "Ramp". If none do, someone typed bare names, one copy each.
    has_quantities = any(
        _parse_line(line_number, line, stripped) is not None
        for line_number, line, stripped in lines
    )

    builder = _Builder()
    for line_number, line, stripped in lines:
        builder.add(line_number, line, stripped, has_quantities)
    return builder.result()


def parse_card_text(text: str) -> CardText | None:
    """Split `Name (SET) 123 *F* [tags]` into the name and its marker.

    `text` is a line with its quantity already removed (or one that never had
    one). Returns None if no name is left, or if something after the name
    isn't a recognized marker or tag.
    """
    name, _, tail = _split_markers(text.strip())
    if tail and _MARKERS.fullmatch(tail) is None:
        return None

    # count=1: there is only ever one printing, at the very end.
    name = _PRINTING.sub("", name, count=1)
    # Nothing left: the text was only a printing ("(C21) 263") or only markers.
    if not name:
        return None
    return CardText(card_name=name, marker=_marker(tail))


def _parse_line(line_number: int, line: str, stripped: str) -> DeckLine | None:
    """The DeckLine for one non-blank line, or None if it isn't one."""
    # fullmatch, not match: the pattern must cover the whole line.
    match = _QUANTITY.fullmatch(stripped)
    if match is None:
        return None

    quantity = int(match["quantity"])
    # "0 Sol Ring" is shaped right but means nothing in a deck. Treat it as
    # unparsed instead of guessing whether the user meant 1 or a removal.
    if quantity == 0:
        return None

    card = parse_card_text(match["rest"])
    if card is None:
        return None

    return DeckLine(
        line_number=line_number,
        quantity=quantity,
        card_name=card.card_name,
        text=line,
        marker=card.marker,
    )


def _split_markers(text: str) -> tuple[str, str, str]:
    """(name part, separator, markers tail), like str.partition."""
    match = _MARKERS_START.search(text)
    if match is None:
        return text, "", ""
    return text[: match.start()], match.group(), text[match.end() :]


def _marker(tail: str) -> LineMarker | None:
    """Which marker, if any, the tail of a line carries.

    "Not in the deck" wins over "commander": a commander Archidekt flags as
    {noDeck} is a maybeboard card, not the one leading this deck.
    """
    lowered = tail.lower()
    if "{nodeck}" in lowered:
        return "maybeboard"
    if "*cmdr*" in lowered or _has_commander_category(tail):
        return "commander"
    if "*cmpn*" in lowered:
        return "companion"
    return None


def _has_commander_category(tail: str) -> bool:
    """Whether an Archidekt [...] tag lists the Commander category.

    Categories are comma-separated and may carry flags in braces, as in
    [Commander{top},Legends]. A category merely containing the word, such
    as [Commander Damage], doesn't count.
    """
    for brackets in re.findall(r"\[([^\]]*)\]", tail):
        for category in brackets.split(","):
            name = re.sub(r"\{[^}]*\}", "", category).strip()
            if name.lower() == "commander":
                return True
    return False


# --- Sections ---------------------------------------------------------------

# Where the lines under a section header belong.
SectionKind = Literal["main_deck", "commander", "ignored"]


@dataclass(frozen=True)
class _Section:
    name: str
    kind: SectionKind


_MAIN_DECK = _Section("Main Deck", "main_deck")

# The section names deck sites use, lowercased, mapped to a tidy name. None of
# these is the name of a real Card (checked against all 35,011 names).
_KNOWN_SECTIONS: dict[str, _Section] = {
    "deck": _MAIN_DECK,
    "main": _MAIN_DECK,
    "main deck": _MAIN_DECK,
    "maindeck": _MAIN_DECK,
    "mainboard": _MAIN_DECK,
    "commander": _Section("Commander", "commander"),
    "commanders": _Section("Commander", "commander"),
    "sideboard": _Section("Sideboard", "ignored"),
    "maybeboard": _Section("Maybeboard", "ignored"),
    "maybe": _Section("Maybeboard", "ignored"),
    "considering": _Section("Considering", "ignored"),
    # A Companion starts the game outside the deck.
    "companion": _Section("Companion", "ignored"),
    # Arena's "About" block holds the deck's name, not cards.
    "about": _Section("About", "ignored"),
}

# MTGO's older "SB: 1 Card" marks a single sideboard line.
_SIDEBOARD_PREFIX = re.compile(r"SB:\s*\S.*", re.IGNORECASE)

# A line that starts like a quantity: "0 Sol Ring", "-1 Sol Ring", "1x",
# "١ Sol Ring". If it didn't parse as a Deck Line, it's a broken card line,
# never a header or a bare card name. \d on purpose here: it also catches
# digits from other scripts.
_QUANTITY_LIKE = re.compile(r"-?\d+[xX]?(?:\s|$)")

# Header decoration to remove before comparing names: a leading "//" or "#"
# (Deckstats, TappedOut), a trailing ":" (Moxfield's "SIDEBOARD:") and a
# trailing count like "(30)".
_HEADER_PREFIX = re.compile(r"^(?://|#)\s*")
_HEADER_SUFFIX = re.compile(r"\s*(?:\(\d+\))?\s*:?\s*$")


class _Builder:
    """Collects lines into sections as parse_deck_list walks the Deck List."""

    def __init__(self) -> None:
        self.section = _MAIN_DECK
        self.main_deck: list[DeckLine] = []
        self.commanders: list[DeckLine] = []
        # A dict keeps first-appearance order, and merges two sections with
        # the same name (a "Maybeboard" header and {noDeck} lines).
        self.ignored: dict[str, list[IgnoredLine]] = {}
        self.unrecognized: list[SectionHeader] = []
        self.unparsed: list[UnparsedLine] = []

    def add(
        self, line_number: int, line: str, stripped: str, has_quantities: bool
    ) -> None:
        if _SIDEBOARD_PREFIX.fullmatch(stripped):
            self._ignore("Sideboard", line_number, line)
            return

        deck_line = _parse_line(line_number, line, stripped)
        if deck_line is None:
            header = self._header(stripped, has_quantities)
            if header is not None:
                self._start_section(header, line_number, line, stripped)
                return
        elif self.section.name == "About":
            # Arena's About block only holds the deck's name. A real card line
            # means it has ended, even if the paste lost the "Deck" header.
            self.section = _MAIN_DECK

        if self.section.kind == "ignored":
            # Everything in an Ignored Section is listed back as typed, so
            # nothing in it needs to parse.
            self._ignore(self.section.name, line_number, line)
            return

        if deck_line is None and not has_quantities:
            deck_line = _parse_bare_name(line_number, line, stripped)
        if deck_line is None:
            self.unparsed.append(UnparsedLine(line_number=line_number, text=line))
            return

        self._place(deck_line)

    def result(self) -> ParsedDeckList:
        return ParsedDeckList(
            main_deck_lines=tuple(self.main_deck),
            commander_lines=tuple(self.commanders),
            ignored_sections=tuple(
                IgnoredSection(name=name, lines=tuple(lines))
                for name, lines in self.ignored.items()
            ),
            unrecognized_headers=tuple(self.unrecognized),
            unparsed_lines=tuple(self.unparsed),
        )

    def _header(self, stripped: str, has_quantities: bool) -> _Section | None:
        """The section this line starts, or None if it isn't a header."""
        if _QUANTITY_LIKE.match(stripped):
            return None

        name = _header_name(stripped)
        known = _KNOWN_SECTIONS.get(name.lower())
        if known is not None:
            return known

        looks_like_a_header = stripped.startswith(("//", "#")) or stripped.endswith(":")
        # In a list with quantities, a line without one is a header. Except
        # inside Arena's About block, whose "Name My Deck" line isn't one.
        if looks_like_a_header or (has_quantities and self.section.name != "About"):
            # An unknown header is a deck site's own grouping of main-deck
            # cards, like "Ramp" or "Creature".
            return _Section(name or stripped, "main_deck")
        return None

    def _start_section(
        self, section: _Section, line_number: int, line: str, stripped: str
    ) -> None:
        self.section = section
        if _KNOWN_SECTIONS.get(_header_name(stripped).lower()) is None:
            self.unrecognized.append(
                SectionHeader(line_number=line_number, text=line, name=section.name)
            )

    def _place(self, deck_line: DeckLine) -> None:
        """Put a card line where its marker, or else its section, says."""
        if deck_line.marker == "maybeboard":
            self._ignore("Maybeboard", deck_line.line_number, deck_line.text)
        elif deck_line.marker == "companion":
            self._ignore("Companion", deck_line.line_number, deck_line.text)
        elif deck_line.marker == "commander" or self.section.kind == "commander":
            self.commanders.append(deck_line)
        else:
            self.main_deck.append(deck_line)

    def _ignore(self, section_name: str, line_number: int, line: str) -> None:
        self.ignored.setdefault(section_name, []).append(
            IgnoredLine(line_number=line_number, text=line)
        )


def _header_name(stripped: str) -> str:
    """A header without its decoration: "//Commander (1):" -> "Commander"."""
    without_prefix = _HEADER_PREFIX.sub("", stripped, count=1)
    return _HEADER_SUFFIX.sub("", without_prefix, count=1)


def _parse_bare_name(line_number: int, line: str, stripped: str) -> DeckLine | None:
    """One copy of the card on a line without a quantity, like "Sol Ring".

    Only used when no line in the list has a quantity. A line that starts
    like a broken quantity ("0 Sol Ring") is never read as a bare name.
    """
    if _QUANTITY_LIKE.match(stripped):
        return None
    card = parse_card_text(stripped)
    if card is None:
        return None
    return DeckLine(
        line_number=line_number,
        quantity=1,
        card_name=card.card_name,
        text=line,
        marker=card.marker,
    )
