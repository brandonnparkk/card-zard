from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy.orm import Session

from card_zard.decks.deck_list import parse_deck_list
from card_zard.decks.resolution import NoSnapshotError, resolve_deck
from card_zard_api.database import get_session
from card_zard_api.schemas import AnalyzeRequest, AnalyzeResponse

app = FastAPI(title="Card Zard")

# Annotated[...] bundles the type with how FastAPI should fill it in, so each
# endpoint just says `session: SessionDep`.
SessionDep = Annotated[Session, Depends(get_session)]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# A plain `def`, not `async def`: SQLAlchemy here is synchronous, and FastAPI
# runs plain functions in a thread pool so they don't block other requests.
@app.post("/analyze")
def analyze(request: AnalyzeRequest, session: SessionDep) -> AnalyzeResponse:
    """Resolve a pasted Deck List against the current Snapshot.

    Lines that can't be matched to exactly one Card come back as Unresolved
    Lines; the rest of the deck still resolves (ADR-0008).
    """
    try:
        deck = resolve_deck(session, parse_deck_list(request.deck_list))
    except NoSnapshotError as error:
        # 503: the request was fine, but the server has no card data to
        # answer it with yet. Someone needs to load a Snapshot.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No card data has been loaded yet.",
        ) from error

    return AnalyzeResponse.from_resolved_deck(deck)
