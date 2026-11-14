"""Tests for splitting a pasted Deck List into Deck Lines (no database needed)."""

import pytest

from card_zard.decks.deck_list import (
    CardText,
    DeckLine,
    IgnoredLine,
    IgnoredSection,
    ParsedDeckList,
    SectionHeader,
    UnparsedLine,
    parse_card_text,
    parse_deck_list,
)

# --- Deck Lines ---


def test_a_single_line_becomes_one_deck_line() -> None:
    assert parse_deck_list("1 Sol Ring") == ParsedDeckList(
        main_deck_lines=(
            DeckLine(
                line_number=1, quantity=1, card_name="Sol Ring", text="1 Sol Ring"
            ),
        ),
        unparsed_lines=(),
    )


def test_quantities_above_one_are_kept() -> None:
    [line] = parse_deck_list("35 Island").main_deck_lines

    assert line.quantity == 35
    assert line.card_name == "Island"


def test_lines_keep_their_order_and_line_numbers() -> None:
    text = "1 Sol Ring\n1 Arcane Signet\n1 Command Tower"

    lines = parse_deck_list(text).main_deck_lines

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
    [line] = parse_deck_list(f"1 {card_name}").main_deck_lines

    assert line.card_name == card_name


def test_repeated_cards_are_not_merged() -> None:
    lines = parse_deck_list("1 Sol Ring\n1 Sol Ring").main_deck_lines

    assert [line.line_number for line in lines] == [1, 2]


# --- Whitespace and line endings ---


def test_blank_and_whitespace_only_lines_are_skipped() -> None:
    parsed = parse_deck_list("\n1 Sol Ring\n   \n\t\n1 Arcane Signet\n\n")

    assert [line.card_name for line in parsed.main_deck_lines] == [
        "Sol Ring",
        "Arcane Signet",
    ]
    assert parsed.unparsed_lines == ()


def test_line_numbers_count_the_skipped_blank_lines() -> None:
    """So "line 3" in a report is line 3 of what the user pasted."""
    [line] = parse_deck_list("\n\n1 Sol Ring").main_deck_lines

    assert line.line_number == 3


def test_windows_line_endings_are_handled() -> None:
    lines = parse_deck_list("1 Sol Ring\r\n1 Arcane Signet\r\n").main_deck_lines

    assert [line.card_name for line in lines] == ["Sol Ring", "Arcane Signet"]


def test_surrounding_and_separating_whitespace_is_not_part_of_the_name() -> None:
    [line] = parse_deck_list("  2 \t Sol Ring  ").main_deck_lines

    assert line.quantity == 2
    assert line.card_name == "Sol Ring"
    # The original text is kept untouched, for quoting back to the user.
    assert line.text == "  2 \t Sol Ring  "


def test_an_empty_deck_list_has_no_lines() -> None:
    assert parse_deck_list("") == ParsedDeckList(main_deck_lines=(), unparsed_lines=())


# --- Lines that aren't Deck Lines ---


@pytest.mark.parametrize(
    "text",
    [
        "1",  # quantity but no name
        "1x",
        "0 Sol Ring",  # a quantity of zero means nothing in a deck
        "0x Sol Ring",
        "-1 Sol Ring",
        "١ Sol Ring",  # Arabic-Indic digit one, not 0-9
        "1 (C21) 263",  # a printing but no name
        "1 Sol Ring *F* extra words",  # text after the markers isn't dropped
        "1 Sol Ring [Ramp] stray",
    ],
)
def test_lines_not_shaped_like_a_deck_line_are_kept_as_unparsed(text: str) -> None:
    parsed = parse_deck_list(text)

    assert parsed.main_deck_lines == ()
    assert parsed.unparsed_lines == (UnparsedLine(line_number=1, text=text),)


def test_unparsed_lines_do_not_stop_the_rest_of_the_deck() -> None:
    parsed = parse_deck_list("1 Sol Ring\n0 Sol Ring\n1 Arcane Signet")

    assert [line.card_name for line in parsed.main_deck_lines] == [
        "Sol Ring",
        "Arcane Signet",
    ]
    assert parsed.unparsed_lines == (UnparsedLine(line_number=2, text="0 Sol Ring"),)


# --- Quantities ---


@pytest.mark.parametrize("text", ["1x Sol Ring", "1X Sol Ring", "1x   Sol Ring"])
def test_an_x_after_the_quantity_is_allowed(text: str) -> None:
    [line] = parse_deck_list(text).main_deck_lines

    assert (line.quantity, line.card_name) == (1, "Sol Ring")


def test_names_starting_with_x_are_not_mistaken_for_the_x() -> None:
    [line] = parse_deck_list("1 Xenagos, God of Revels").main_deck_lines

    assert line.card_name == "Xenagos, God of Revels"


def test_names_starting_with_digits_keep_them() -> None:
    [line] = parse_deck_list("1 1996 World Champion").main_deck_lines

    assert (line.quantity, line.card_name) == (1, "1996 World Champion")


# --- Printings are dropped (ADR-0006) ---


@pytest.mark.parametrize(
    ("text", "card_name"),
    [
        # Moxfield: uppercase set, any collector-number shape
        ("1 Sol Ring (C21) 263", "Sol Ring"),
        ("1 Arcane Signet (SLD) 1492★", "Arcane Signet"),
        ("2 Lightning Bolt (PLST) E01-54", "Lightning Bolt"),
        ("1 Culling the Weak (PMEI) 2023-8", "Culling the Weak"),
        ("1 Beseech the Mirror (PWOE) 82s", "Beseech the Mirror"),
        # Archidekt: lowercase set; its Arena export: empty set
        ("1x Drag to the Roots (dsk) 213", "Drag to the Roots"),
        ("1 Deadly Tempest () 19", "Deadly Tempest"),
        # A set with no collector number, and TappedOut's (SET:id)
        ("1x Llanowar Elves (M10)", "Llanowar Elves"),
        ("1x Mox Pearl (ATQ:1074)", "Mox Pearl"),
        # Multi-faced names keep their " // "
        (
            "1x Invasion of Ikoria // Zilortha, Apex of Ikoria (mom) 190",
            "Invasion of Ikoria // Zilortha, Apex of Ikoria",
        ),
    ],
)
def test_the_set_code_and_collector_number_are_dropped(
    text: str, card_name: str
) -> None:
    [line] = parse_deck_list(text).main_deck_lines

    assert line.card_name == card_name
    assert line.text == text


@pytest.mark.parametrize(
    ("text", "card_name"),
    [
        # Real Card Names that end in parentheses. Mixed case or spaces mean
        # it isn't a set code, so it stays part of the name.
        ("1 Hazmat Suit (Used)", "Hazmat Suit (Used)"),
        ("1 B.F.M. (Big Furry Monster)", "B.F.M. (Big Furry Monster)"),
        # ...and with a real printing after it, only the printing goes.
        ("1 Hazmat Suit (Used) (UNF) 123", "Hazmat Suit (Used)"),
    ],
)
def test_parentheses_that_are_part_of_a_card_name_are_kept(
    text: str, card_name: str
) -> None:
    [line] = parse_deck_list(text).main_deck_lines

    assert line.card_name == card_name


# --- Finishes and tags are dropped ---


@pytest.mark.parametrize(
    "text",
    [
        "1 Sol Ring (C21) 263 *F*",  # Moxfield foil
        "1 Sol Ring (C21) 263 *E*",  # etched
        "1x Sol Ring *F:pre*",  # TappedOut prerelease foil
        "1x Sol Ring (c21) 263 [Ramp]",  # Archidekt category
        "1x Sol Ring (c21) 263 *F* [Ramp,Artifacts] ^Have,#37d67a^",
        "1 Sol Ring (C21) 263 *F* #ramp #!fast mana",  # Moxfield tags
    ],
)
def test_finish_markers_and_tags_are_dropped(text: str) -> None:
    [line] = parse_deck_list(text).main_deck_lines

    assert line.card_name == "Sol Ring"
    assert line.marker is None


# --- Markers that say where a card belongs ---


@pytest.mark.parametrize(
    "text",
    [
        "1x Greven Il-Vec *CMDR*",  # TappedOut
        "1x Greven Il-Vec (ddn) 47 *F* [Commander{top}]",  # Archidekt
        "1 Greven Il-Vec [Commander]",  # EDHREC's link to Archidekt
        "1x Greven Il-Vec [Legends,Commander{top}]",
    ],
)
def test_a_commander_marker_puts_the_line_with_the_commanders(text: str) -> None:
    parsed = parse_deck_list(f"1 Sol Ring\n{text}")

    [line] = parsed.commander_lines
    assert line.card_name == "Greven Il-Vec"
    assert line.marker == "commander"
    assert [line.card_name for line in parsed.main_deck_lines] == ["Sol Ring"]


def test_a_category_only_mentioning_commander_is_not_a_marker() -> None:
    [line] = parse_deck_list("1x Sol Ring [Commander Damage]").main_deck_lines

    assert line.marker is None


def test_the_companion_marker_puts_the_line_in_a_companion_section() -> None:
    parsed = parse_deck_list("1x Lurrus of the Dream-Den *CMPN*")

    assert parsed.main_deck_lines == ()
    assert parsed.ignored_sections == (
        IgnoredSection(
            name="Companion",
            lines=(IgnoredLine(1, "1x Lurrus of the Dream-Den *CMPN*"),),
        ),
    )


def test_archidekts_no_deck_flag_puts_the_line_in_the_maybeboard() -> None:
    text = "1x Aspect of Mongoose (tsp) 191 [Maybeboard{noDeck}{noPrice},Potions]"

    parsed = parse_deck_list(f"1x Sol Ring\n{text}")

    assert [line.card_name for line in parsed.main_deck_lines] == ["Sol Ring"]
    assert parsed.ignored_sections == (
        IgnoredSection(name="Maybeboard", lines=(IgnoredLine(2, text),)),
    )


def test_no_deck_wins_over_commander() -> None:
    """A commander flagged as out of the deck is a maybeboard card."""
    parsed = parse_deck_list("1x Greven Il-Vec [Commander{noDeck}]")

    assert parsed.commander_lines == ()
    assert [s.name for s in parsed.ignored_sections] == ["Maybeboard"]


# --- parse_card_text on its own ---


def test_parse_card_text_reads_a_line_without_a_quantity() -> None:
    assert parse_card_text("Sol Ring (C21) 263 *CMDR*") == CardText(
        card_name="Sol Ring", marker="commander"
    )


@pytest.mark.parametrize("text", ["", "   ", "*F*", "[Ramp]", "Sol Ring *F* oops"])
def test_parse_card_text_returns_none_without_a_clean_name(text: str) -> None:
    assert parse_card_text(text) is None


# --- Section headers ---


def names(lines: tuple[DeckLine, ...]) -> list[str]:
    return [line.card_name for line in lines]


@pytest.mark.parametrize(
    "header",
    [
        "Sideboard",
        "sideboard",
        "SIDEBOARD:",  # Moxfield
        "Sideboard:",  # TappedOut
        "//Sideboard",  # Deckstats
        "// Sideboard",
        "Sideboard (2)",
    ],
)
def test_known_headers_are_recognized_in_any_form(header: str) -> None:
    parsed = parse_deck_list(f"1 Sol Ring\n{header}\n1 Mana Crypt\n1 Mana Vault")

    assert names(parsed.main_deck_lines) == ["Sol Ring"]
    [section] = parsed.ignored_sections
    assert section.name == "Sideboard"
    assert [line.text for line in section.lines] == ["1 Mana Crypt", "1 Mana Vault"]
    assert parsed.unrecognized_headers == ()


@pytest.mark.parametrize("header", ["Maybeboard", "Maybe", "Considering", "Companion"])
def test_each_ignored_section_keeps_its_own_name(header: str) -> None:
    [section] = parse_deck_list(f"{header}\n1 Sol Ring").ignored_sections

    assert section.name == ("Maybeboard" if header == "Maybe" else header)


@pytest.mark.parametrize("header", ["Deck", "Main", "Mainboard", "Main Deck", "DECK:"])
def test_main_deck_headers_lead_back_to_the_main_deck(header: str) -> None:
    parsed = parse_deck_list(
        f"Commander\n1 Atraxa, Praetors' Voice\n{header}\n1 Sol Ring"
    )

    assert names(parsed.commander_lines) == ["Atraxa, Praetors' Voice"]
    assert names(parsed.main_deck_lines) == ["Sol Ring"]
    assert parsed.unrecognized_headers == ()


def test_lines_under_a_commander_header_are_kept_apart() -> None:
    parsed = parse_deck_list(
        "Commander\n1 Thrasios, Triton Hero\n1 Tymna the Weaver\nDeck\n1 Sol Ring"
    )

    assert names(parsed.commander_lines) == [
        "Thrasios, Triton Hero",
        "Tymna the Weaver",
    ]
    assert names(parsed.main_deck_lines) == ["Sol Ring"]


def test_blank_lines_do_not_end_a_section() -> None:
    parsed = parse_deck_list("1 Sol Ring\n\nSideboard\n1 Mana Crypt\n\n1 Mana Vault")

    [section] = parsed.ignored_sections
    assert len(section.lines) == 2


def test_ignored_section_lines_are_kept_even_if_they_do_not_parse() -> None:
    parsed = parse_deck_list("1 Sol Ring\nSideboard\n1 Sol Ring *F* oops")

    assert parsed.unparsed_lines == ()
    assert parsed.ignored_sections[0].lines == (IgnoredLine(3, "1 Sol Ring *F* oops"),)


def test_sections_with_the_same_name_are_merged() -> None:
    parsed = parse_deck_list(
        "1x Sol Ring\n1x Brainstorm [Draw{noDeck}]\nMaybeboard\n1x Ponder"
    )

    assert parsed.ignored_sections == (
        IgnoredSection(
            name="Maybeboard",
            lines=(
                IgnoredLine(2, "1x Brainstorm [Draw{noDeck}]"),
                IgnoredLine(4, "1x Ponder"),
            ),
        ),
    )


def test_an_sb_prefix_marks_a_sideboard_line() -> None:
    parsed = parse_deck_list("1 Sol Ring\nSB: 1 Mana Crypt")

    assert names(parsed.main_deck_lines) == ["Sol Ring"]
    assert parsed.ignored_sections == (
        IgnoredSection(name="Sideboard", lines=(IgnoredLine(2, "SB: 1 Mana Crypt"),)),
    )


# --- Unknown headers ---


@pytest.mark.parametrize(
    ("header", "name"),
    [
        ("Ramp", "Ramp"),  # Archidekt category
        ("Counterspell", "Counterspell"),  # also a Card Name: still a header here
        ("//Draw / Advantage", "Draw / Advantage"),  # Deckstats category
        ("Creature", "Creature"),  # Archidekt card-type header
        ("Creatures (30)", "Creatures"),
        ("# WinCon", "WinCon"),  # TappedOut
    ],
)
def test_unknown_headers_keep_their_cards_in_the_main_deck(
    header: str, name: str
) -> None:
    parsed = parse_deck_list(f"1 Sol Ring\n{header}\n1 Arcane Signet")

    assert names(parsed.main_deck_lines) == ["Sol Ring", "Arcane Signet"]
    assert parsed.unrecognized_headers == (
        SectionHeader(line_number=2, text=header, name=name),
    )


def test_an_unknown_header_after_the_sideboard_returns_to_the_main_deck() -> None:
    """Deckstats lists categories after other sections; they're all main deck."""
    parsed = parse_deck_list("//Sideboard\n1 Mana Crypt\n//Ramp\n1 Sol Ring")

    assert names(parsed.main_deck_lines) == ["Sol Ring"]


# --- Lines without a quantity ---


def test_with_no_quantities_anywhere_each_line_is_one_copy() -> None:
    parsed = parse_deck_list("Sol Ring\nArcane Signet (C21) 263 *F*")

    assert [(line.quantity, line.card_name) for line in parsed.main_deck_lines] == [
        (1, "Sol Ring"),
        (1, "Arcane Signet"),
    ]
    assert parsed.unrecognized_headers == ()


def test_known_headers_still_count_in_a_list_without_quantities() -> None:
    parsed = parse_deck_list("Commander\nAtraxa, Praetors' Voice\nDeck\nSol Ring")

    assert names(parsed.commander_lines) == ["Atraxa, Praetors' Voice"]
    assert names(parsed.main_deck_lines) == ["Sol Ring"]


def test_a_broken_quantity_in_a_bare_name_list_is_not_read_as_a_name() -> None:
    """ "0 Arcane Signet" isn't a card called "0 Arcane Signet": report it."""
    parsed = parse_deck_list("Sol Ring\n0 Arcane Signet")

    assert names(parsed.main_deck_lines) == ["Sol Ring"]
    assert [line.text for line in parsed.unparsed_lines] == ["0 Arcane Signet"]


def test_a_name_starting_with_a_number_reads_as_a_quantity_without_one() -> None:
    """A known limit: "1996 World Champion" alone means 1996 copies of a card
    named "World Champion", which resolution then reports as unmatched. With
    its quantity ("1 1996 World Champion") it parses correctly."""
    [line] = parse_deck_list("1996 World Champion").main_deck_lines

    assert (line.quantity, line.card_name) == (1996, "World Champion")


def test_with_quantities_a_line_without_one_is_a_header_not_a_card() -> None:
    parsed = parse_deck_list("1 Sol Ring\nArcane Signet\n1 Command Tower")

    assert names(parsed.main_deck_lines) == ["Sol Ring", "Command Tower"]
    assert [h.name for h in parsed.unrecognized_headers] == ["Arcane Signet"]


# --- Whole exports, as deck sites produce them ---


def test_an_arena_export() -> None:
    parsed = parse_deck_list(
        "About\nName  My Atraxa Deck\n\nCommander\n1 Atraxa, Praetors' Voice\n\n"
        "Deck\n1 Sol Ring\n1 Arcane Signet\n\nSideboard\n1 Mana Crypt\n"
    )

    assert names(parsed.commander_lines) == ["Atraxa, Praetors' Voice"]
    assert names(parsed.main_deck_lines) == ["Sol Ring", "Arcane Signet"]
    assert [(s.name, len(s.lines)) for s in parsed.ignored_sections] == [
        ("About", 1),
        ("Sideboard", 1),
    ]
    assert parsed.unrecognized_headers == ()
    assert parsed.unparsed_lines == ()


def test_arenas_about_block_ends_at_the_first_card_line() -> None:
    parsed = parse_deck_list("About\nName My Deck\n1 Sol Ring")

    assert names(parsed.main_deck_lines) == ["Sol Ring"]


def test_a_moxfield_export_does_not_guess_the_unmarked_commander() -> None:
    """Moxfield puts the commander first with no header: it stays unknown."""
    parsed = parse_deck_list(
        "1 Najeela, the Blade-Blossom (BBD) 62 *F*\n1 Ad Nauseam (ALA) 63 *F*\n"
        "\nSIDEBOARD:\n1 Gaea's Cradle (USG) 321\n"
    )

    assert parsed.commander_lines == ()
    assert names(parsed.main_deck_lines) == [
        "Najeela, the Blade-Blossom",
        "Ad Nauseam",
    ]
    assert [s.name for s in parsed.ignored_sections] == ["Sideboard"]


def test_a_deckstats_export() -> None:
    parsed = parse_deck_list(
        "//Commander\n1 K'rrik, Son of Yawgmoth (PJ21) 2\n\n"
        "//Tutor\n1 Beseech the Mirror (PWOE) 82s\n\n"
        "//Maybeboard\n1 Sign in Blood (PLIST) M10-112\n"
    )

    assert names(parsed.commander_lines) == ["K'rrik, Son of Yawgmoth"]
    assert names(parsed.main_deck_lines) == ["Beseech the Mirror"]
    assert [s.name for s in parsed.ignored_sections] == ["Maybeboard"]
    assert [h.name for h in parsed.unrecognized_headers] == ["Tutor"]


def test_an_archidekt_export_without_headers() -> None:
    parsed = parse_deck_list(
        "1x Baba Lysaga, Night Witch (clb) 525 *E* [Commander{top}]\n"
        "1x Drag to the Roots (dsk) 213 *F* [Disruption]\n"
        "1x Aspect of Mongoose (tsp) 191 [Maybeboard{noDeck}{noPrice},Potions]\n"
    )

    assert names(parsed.commander_lines) == ["Baba Lysaga, Night Witch"]
    assert names(parsed.main_deck_lines) == ["Drag to the Roots"]
    assert [s.name for s in parsed.ignored_sections] == ["Maybeboard"]
