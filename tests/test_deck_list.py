"""Tests for splitting a pasted Deck List into Deck Lines (no database needed)."""

import pytest

from card_zard.decks.deck_list import (
    DeckLine,
    ParsedDeckList,
    UnparsedLine,
    parse_deck_list,
)

# --- Deck Lines ---


def test_a_single_line_becomes_one_deck_line() -> None:
    assert parse_deck_list("1 Sol Ring") == ParsedDeckList(
        deck_lines=(
            DeckLine(
                line_number=1, quantity=1, card_name="Sol Ring", text="1 Sol Ring"
            ),
        ),
        unparsed_lines=(),
    )


def test_quantities_above_one_are_kept() -> None:
    [line] = parse_deck_list("35 Island").deck_lines

    assert line.quantity == 35
    assert line.card_name == "Island"


def test_lines_keep_their_order_and_line_numbers() -> None:
    text = "1 Sol Ring\n1 Arcane Signet\n1 Command Tower"

    lines = parse_deck_list(text).deck_lines

    assert [(line.line_number, line.card_name) for line in lines] == [
        (1, "Sol Ring"),
        (2, "Arcane Signet"),
        (3, "Command Tower"),
    ]


@pytest.mark.parametrize(
    "card_name",
    [
        "Fire // Ice",
        "Nazgûl",
        "Borrowing 100,000 Arrows",
        "Fable of the Mirror-Breaker // Reflection of Kiki-Jiki",
    ],
)
def test_card_names_are_kept_exactly_as_typed(card_name: str) -> None:
    [line] = parse_deck_list(f"1 {card_name}").deck_lines

    assert line.card_name == card_name


def test_repeated_cards_are_not_merged() -> None:
    lines = parse_deck_list("1 Sol Ring\n1 Sol Ring").deck_lines

    assert [line.line_number for line in lines] == [1, 2]


# --- Whitespace and line endings ---


def test_blank_and_whitespace_only_lines_are_skipped() -> None:
    parsed = parse_deck_list("\n1 Sol Ring\n   \n\t\n1 Arcane Signet\n\n")

    assert [line.card_name for line in parsed.deck_lines] == [
        "Sol Ring",
        "Arcane Signet",
    ]
    assert parsed.unparsed_lines == ()


def test_line_numbers_count_the_skipped_blank_lines() -> None:
    """So "line 3" in a report is line 3 of what the user pasted."""
    [line] = parse_deck_list("\n\n1 Sol Ring").deck_lines

    assert line.line_number == 3


def test_windows_line_endings_are_handled() -> None:
    lines = parse_deck_list("1 Sol Ring\r\n1 Arcane Signet\r\n").deck_lines

    assert [line.card_name for line in lines] == ["Sol Ring", "Arcane Signet"]


def test_surrounding_and_separating_whitespace_is_not_part_of_the_name() -> None:
    [line] = parse_deck_list("  2 \t Sol Ring  ").deck_lines

    assert line.quantity == 2
    assert line.card_name == "Sol Ring"
    # The original text is kept untouched, for quoting back to the user.
    assert line.text == "  2 \t Sol Ring  "


def test_an_empty_deck_list_has_no_lines() -> None:
    assert parse_deck_list("") == ParsedDeckList(deck_lines=(), unparsed_lines=())


# --- Lines that aren't Deck Lines (yet) ---


@pytest.mark.parametrize(
    "text",
    [
        "Sol Ring",  # no quantity: issue #4 decides it means 1
        "1x Sol Ring",  # issue #4
        "Sideboard",  # section header: issue #4
        "1",  # quantity but no name
        "0 Sol Ring",  # a quantity of zero means nothing in a deck
        "-1 Sol Ring",
        "١ Sol Ring",  # Arabic-Indic digit one, not 0-9
    ],
)
def test_lines_not_shaped_like_a_deck_line_are_kept_as_unparsed(text: str) -> None:
    parsed = parse_deck_list(text)

    assert parsed.deck_lines == ()
    assert parsed.unparsed_lines == (UnparsedLine(line_number=1, text=text),)


def test_unparsed_lines_do_not_stop_the_rest_of_the_deck() -> None:
    parsed = parse_deck_list("1 Sol Ring\nSideboard\n1 Arcane Signet")

    assert [line.card_name for line in parsed.deck_lines] == [
        "Sol Ring",
        "Arcane Signet",
    ]
    assert parsed.unparsed_lines == (UnparsedLine(line_number=2, text="Sideboard"),)
