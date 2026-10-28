# v1 has no accounts; accounts are the first priority after v1

v1 is fully anonymous: users paste or import a Deck List, get an Analysis, and can share it with a Share Link. Building auth first would delay everything else, and Scryfall's terms (ADR-0004) require anonymous access to card data anyway. Accounts and saved decks are the first priority after v1, before the LLM phase, because per-user limits are needed once LLM calls cost real money. They will use a managed auth provider rather than hand-built auth. Until then, rate limiting is per IP address.
