"""The JSON shapes of API requests and responses.

These are Pydantic models, kept apart from the core's dataclasses and the
database models (ADR-0009): the core can change its internals without
changing what the API promises, and the other way round.
"""

from uuid import UUID

from pydantic import BaseModel, Field

from card_zard.decks.resolution import ResolvedCard, ResolvedDeck, UnresolvedReason

# A 100-card Commander deck pasted with set codes is about 4,000 characters.
# 100,000 leaves plenty of room for messy pastes while refusing megabytes.
MAX_DECK_LIST_LENGTH = 100_000


class AnalyzeRequest(BaseModel):
    deck_list: str = Field(
        max_length=MAX_DECK_LIST_LENGTH,
        description=(
            "The Deck List as pasted or exported from a deck site, one card per"
            " line, with optional section headers such as `Commander` or"
            " `Sideboard`."
        ),
        examples=["Commander\n1 Atraxa, Praetors' Voice\n\nDeck\n1 Sol Ring (C21) 263"],
    )


class ResolvedCardOut(BaseModel):
    oracle_id: UUID
    card_name: str
    quantity: int

    @classmethod
    def from_card(cls, card: ResolvedCard) -> "ResolvedCardOut":
        return cls(
            oracle_id=card.oracle_id, card_name=card.card_name, quantity=card.quantity
        )


class UnresolvedLineOut(BaseModel):
    line_number: int
    text: str
    reason: UnresolvedReason


class LineOut(BaseModel):
    """A line quoted back exactly as typed."""

    line_number: int
    text: str


class IgnoredSectionOut(BaseModel):
    """A Sideboard, Maybeboard or similar: listed back, not analyzed."""

    name: str
    lines: list[LineOut]


class SectionHeaderOut(BaseModel):
    """A header that isn't a known section; its cards stay in the Main Deck."""

    line_number: int
    text: str
    name: str


class AnalyzeResponse(BaseModel):
    snapshot_version: str
    # Empty when the Deck List didn't mark a Commander. It's never guessed.
    commanders: list[ResolvedCardOut]
    main_deck: list[ResolvedCardOut]
    unresolved_lines: list[UnresolvedLineOut]
    ignored_sections: list[IgnoredSectionOut]
    unrecognized_headers: list[SectionHeaderOut]

    @classmethod
    def from_resolved_deck(cls, deck: ResolvedDeck) -> "AnalyzeResponse":
        """Copy a core ResolvedDeck into the API's response shape."""
        return cls(
            snapshot_version=deck.snapshot_version,
            commanders=[ResolvedCardOut.from_card(card) for card in deck.commanders],
            main_deck=[ResolvedCardOut.from_card(card) for card in deck.main_deck],
            unresolved_lines=[
                UnresolvedLineOut(
                    line_number=line.line_number, text=line.text, reason=line.reason
                )
                for line in deck.unresolved_lines
            ],
            ignored_sections=[
                IgnoredSectionOut(
                    name=section.name,
                    lines=[
                        LineOut(line_number=line.line_number, text=line.text)
                        for line in section.lines
                    ],
                )
                for section in deck.ignored_sections
            ],
            unrecognized_headers=[
                SectionHeaderOut(
                    line_number=header.line_number,
                    text=header.text,
                    name=header.name,
                )
                for header in deck.unrecognized_headers
            ],
        )
