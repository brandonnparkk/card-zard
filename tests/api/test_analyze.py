"""End-to-end tests for POST /analyze against the fixture Snapshot."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from card_zard.snapshots.loader import load_snapshot
from card_zard.snapshots.models import Snapshot
from card_zard_api.database import get_session
from card_zard_api.main import app
from card_zard_api.schemas import MAX_DECK_LIST_LENGTH

pytestmark = pytest.mark.db

FIXTURE = Path(__file__).parent.parent / "fixtures" / "oracle-cards-sample.jsonl"


@pytest.fixture
def client(session: Session) -> Iterator[TestClient]:
    """A client whose requests use this test's rolled-back session.

    dependency_overrides swaps get_session for the test session, so requests
    see whatever the test loaded and nothing outlives the test.
    """
    app.dependency_overrides[get_session] = lambda: session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def snapshot(session: Session) -> Snapshot:
    return load_snapshot(session, FIXTURE)


def analyze(client: TestClient, deck_list: str) -> dict:
    response = client.post("/analyze", json={"deck_list": deck_list})
    assert response.status_code == 200, response.text
    return response.json()


def test_one_sol_ring_returns_the_card_and_the_snapshot_version(
    client: TestClient, session: Session, snapshot: Snapshot
) -> None:
    sol_ring_id = session.execute(
        text("SELECT oracle_id FROM cards WHERE name = 'Sol Ring'")
    ).scalar_one()

    body = analyze(client, "1 Sol Ring")

    assert body == {
        "snapshot_version": snapshot.version,
        "commanders": [],
        "main_deck": [
            {"oracle_id": str(sol_ring_id), "card_name": "Sol Ring", "quantity": 1}
        ],
        "unresolved_lines": [],
        "ignored_sections": [],
        "unrecognized_headers": [],
    }


def test_an_unknown_name_is_reported_and_the_rest_still_resolves(
    client: TestClient, snapshot: Snapshot
) -> None:
    body = analyze(client, "1 Sol Ring\n1 Sol Rnig\n1 Arcane Signet")

    assert [card["card_name"] for card in body["main_deck"]] == [
        "Sol Ring",
        "Arcane Signet",
    ]
    assert body["unresolved_lines"] == [
        {"line_number": 2, "text": "1 Sol Rnig", "reason": "no_matching_card"}
    ]


def test_blank_lines_are_ignored(client: TestClient, snapshot: Snapshot) -> None:
    body = analyze(client, "\n1 Sol Ring\n\n   \n1 Command Tower\n")

    assert [card["card_name"] for card in body["main_deck"]] == [
        "Sol Ring",
        "Command Tower",
    ]
    assert body["unresolved_lines"] == []


def test_windows_line_endings_from_a_browser_paste_work(
    client: TestClient, snapshot: Snapshot
) -> None:
    body = analyze(client, "1 Sol Ring\r\n1 Command Tower\r\n")

    assert len(body["main_deck"]) == 2


def test_an_empty_deck_list_returns_an_empty_deck(
    client: TestClient, snapshot: Snapshot
) -> None:
    body = analyze(client, "")

    assert body["main_deck"] == []
    assert body["unresolved_lines"] == []


def test_no_snapshot_loaded_returns_503(client: TestClient) -> None:
    response = client.post("/analyze", json={"deck_list": "1 Sol Ring"})

    assert response.status_code == 503
    assert response.json() == {"detail": "No card data has been loaded yet."}


@pytest.mark.parametrize(
    "payload",
    [
        {},  # no deck_list
        {"deck_list": 1},  # not a string
        {"deck_list": "1" * (MAX_DECK_LIST_LENGTH + 1)},  # too long
    ],
)
def test_a_bad_request_body_returns_422(
    client: TestClient, snapshot: Snapshot, payload: dict
) -> None:
    response = client.post("/analyze", json=payload)

    assert response.status_code == 422


# --- Deck Lists as deck sites export them (issue #4) ---


def card_names(cards: list[dict]) -> list[str]:
    return [card["card_name"] for card in cards]


@pytest.mark.parametrize("line", ["1 Sol Ring (C21) 263", "1x Sol Ring"])
def test_set_codes_and_1x_resolve_to_the_card_with_quantity_one(
    client: TestClient, snapshot: Snapshot, line: str
) -> None:
    body = analyze(client, line)

    assert [(c["card_name"], c["quantity"]) for c in body["main_deck"]] == [
        ("Sol Ring", 1)
    ]
    assert body["unresolved_lines"] == []


def test_a_list_without_quantities_counts_each_line_once(
    client: TestClient, snapshot: Snapshot
) -> None:
    body = analyze(client, "Sol Ring\nArcane Signet")

    assert [(c["card_name"], c["quantity"]) for c in body["main_deck"]] == [
        ("Sol Ring", 1),
        ("Arcane Signet", 1),
    ]


def test_commander_and_ignored_sections_are_kept_out_of_the_main_deck(
    client: TestClient, snapshot: Snapshot
) -> None:
    body = analyze(
        client,
        "COMMANDER:\n1 Atraxa, Praetors' Voice\n\nDeck\n1 Sol Ring\n\n"
        "sideboard\n1 Mana Crypt\n\n//Maybeboard\n1 Cultivate\n",
    )

    assert card_names(body["commanders"]) == ["Atraxa, Praetors' Voice"]
    assert card_names(body["main_deck"]) == ["Sol Ring"]
    assert body["ignored_sections"] == [
        {"name": "Sideboard", "lines": [{"line_number": 8, "text": "1 Mana Crypt"}]},
        {"name": "Maybeboard", "lines": [{"line_number": 11, "text": "1 Cultivate"}]},
    ]
    assert body["unresolved_lines"] == []


def test_a_partner_pair_under_a_commander_header_are_both_commanders(
    client: TestClient, snapshot: Snapshot
) -> None:
    body = analyze(
        client,
        "Commander\n1 Thrasios, Triton Hero\n1 Tymna the Weaver\nDeck\n1 Sol Ring",
    )

    assert card_names(body["commanders"]) == [
        "Thrasios, Triton Hero",
        "Tymna the Weaver",
    ]


def test_an_unmatched_commander_is_an_unresolved_line(
    client: TestClient, snapshot: Snapshot
) -> None:
    body = analyze(client, "Commander\n1 Atraxa, Praetors Voice\nDeck\n1 Sol Ring")

    assert body["commanders"] == []
    assert body["unresolved_lines"] == [
        {
            "line_number": 2,
            "text": "1 Atraxa, Praetors Voice",
            "reason": "no_matching_card",
        }
    ]


def test_unknown_headers_are_listed_and_their_cards_kept(
    client: TestClient, snapshot: Snapshot
) -> None:
    body = analyze(client, "1 Sol Ring\nRamp\n1 Arcane Signet\n1 Cultivate")

    assert card_names(body["main_deck"]) == ["Sol Ring", "Arcane Signet", "Cultivate"]
    assert body["unrecognized_headers"] == [
        {"line_number": 2, "text": "Ramp", "name": "Ramp"}
    ]


def test_a_line_that_cannot_be_parsed_is_never_dropped(
    client: TestClient, snapshot: Snapshot
) -> None:
    body = analyze(client, "1 Sol Ring\n1 Arcane Signet *F* stray words")

    assert body["unresolved_lines"] == [
        {
            "line_number": 2,
            "text": "1 Arcane Signet *F* stray words",
            "reason": "not_a_deck_line",
        }
    ]


def test_an_archidekt_export(client: TestClient, snapshot: Snapshot) -> None:
    body = analyze(
        client,
        "1x Atraxa, Praetors' Voice (c16) 28 *F* [Commander{top}]\n"
        "1x Sol Ring (c21) 263 [Ramp] ^Have,#37d67a^\n"
        "1x Cultivate (m21) 177 [Maybeboard{noDeck}{noPrice},Ramp]\n",
    )

    assert card_names(body["commanders"]) == ["Atraxa, Praetors' Voice"]
    assert card_names(body["main_deck"]) == ["Sol Ring"]
    assert [s["name"] for s in body["ignored_sections"]] == ["Maybeboard"]


def test_a_moxfield_export(client: TestClient, snapshot: Snapshot) -> None:
    """The commander has no header in Moxfield's own export, so it isn't
    guessed: it stays in the Main Deck and the commanders list is empty."""
    body = analyze(
        client,
        "1 Atraxa, Praetors' Voice (C16) 28 *F*\n1 Sol Ring (C21) 263\n"
        "1 Arcane Signet (SLD) 1492★ *F*\n\nSIDEBOARD:\n1 Mana Crypt (2XM) 270\n",
    )

    assert body["commanders"] == []
    assert card_names(body["main_deck"]) == [
        "Atraxa, Praetors' Voice",
        "Sol Ring",
        "Arcane Signet",
    ]
    assert [s["name"] for s in body["ignored_sections"]] == ["Sideboard"]
