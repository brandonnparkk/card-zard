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
        "main_deck": [
            {"oracle_id": str(sol_ring_id), "card_name": "Sol Ring", "quantity": 1}
        ],
        "unresolved_lines": [],
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
