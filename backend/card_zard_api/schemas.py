"""The JSON shapes of API requests and responses.

These are Pydantic models, kept apart from the core's dataclasses and the
database models (ADR-0009): the core can change its internals without
changing what the API promises, and the other way round.
"""

from uuid import UUID

from pydantic import BaseModel, Field

from card_zard.decks.resolution import ResolvedDeck, UnresolvedReason

# A 100-card Commander deck pasted with set codes is about 4,000 characters.
# 100,000 leaves plenty of room for messy pastes while refusing megabytes.
MAX_DECK_LIST_LENGTH = 100_000


class AnalyzeRequest(BaseModel):
    deck_list: str = Field(
        max_length=MAX_DECK_LIST_LENGTH,
        description="The Deck List as pasted, one `<quantity> <Card Name>` per line.",
        examples=["1 Sol Ring\n1 Arcane Signet"],
    )


class ResolvedCardOut(BaseModel):
    oracle_id: UUID
    card_name: str
    quantity: int


class UnresolvedLineOut(BaseModel):
    line_number: int
    text: str
    reason: UnresolvedReason


class AnalyzeResponse(BaseModel):
    snapshot_version: str
    main_deck: list[ResolvedCardOut]
    unresolved_lines: list[UnresolvedLineOut]

    @classmethod
    def from_resolved_deck(cls, deck: ResolvedDeck) -> "AnalyzeResponse":
        """Copy a core ResolvedDeck into the API's response shape."""
        return cls(
            snapshot_version=deck.snapshot_version,
            main_deck=[
                ResolvedCardOut(
                    oracle_id=card.oracle_id,
                    card_name=card.card_name,
                    quantity=card.quantity,
                )
                for card in deck.main_deck
            ],
            unresolved_lines=[
                UnresolvedLineOut(
                    line_number=line.line_number, text=line.text, reason=line.reason
                )
                for line in deck.unresolved_lines
            ],
        )
