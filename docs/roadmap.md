# Roadmap

Settled on 2026-10-27. Terms are defined in [GLOSSARY.md](../GLOSSARY.md); the reasons behind the major decisions are in [docs/adr/](adr/).

## Phases

- **Phase 1, deterministic analysis.** Counts, Roles and cited Verdicts, with no LLM. Shipping it publicly is v1.
- **Phase 2, LLM explanations.** The LLM chooses which analyses to run as tools and explains the results ([ADR-0001](adr/0001-deterministic-first-verdicts-from-cited-rules.md), [ADR-0012](adr/0012-llm-via-anthropic-sdk-tool-use.md)).
- **Phase 3, retrieval.** `pgvector` search for questions that structured queries can't answer, such as "cards that could improve my deck" ([ADR-0005](adr/0005-postgres-for-everything.md)).

## Order of work after v1

1. Accounts and saved decks, using a managed auth provider ([ADR-0011](adr/0011-no-accounts-in-v1.md)).
2. Phase 2, with a free daily LLM limit per user ([ADR-0004](adr/0004-scryfall-data-use-constraints.md)).
3. Moxfield import, only after confirming Moxfield's API access rules.
4. Phase 3.

## Milestones to v1

Each milestone ends with something that works and is tested.

### M1: `POST /analyze`

- Postgres (with `pgvector` available) running in Docker, schema managed by Alembic.
- A command that loads a Snapshot from Scryfall's `oracle_cards` bulk file, building on `backend/scripts/download_scryfall.py`.
- Deck List parsing for pasted text: quantities, set codes and collector numbers (ignored), `Commander` section headers, and Ignored Sections.
- Card resolution: exact match (ignoring case and accents), then Front-Face Name, then Unresolved Lines with fuzzy suggestions ([ADR-0008](adr/0008-never-silently-guess-deck-contents.md)).
- Commanders from the request's optional `commanders` field or a `Commander` section, including Commander Pairs.
- Counts: Lands, MDFC Lands, Land Sources and Nonland Sources per color, mana curve.
- Legality: Color Identity, singleton (with basic-land and "any number" exceptions) and the Commander banned list.
- The response includes the Snapshot version, Unresolved Lines and Ignored Sections.
- Tooling: Python 3.13, uv with `pyproject.toml`, ruff, pytest and pyright, all run by GitHub Actions.
- A checked-in set of about 50–100 real cards covering the edge cases (MDFCs, split cards, fetchlands, Commander Pairs, banned cards). Only the ingestion integration test reads the full bulk file.

### M2: Roles and Rules

- Load `oracle_tags` into the Snapshot and map them onto the Roles, with a checked-in overrides file ([ADR-0007](adr/0007-roles-from-scryfall-oracle-tags.md)).
- The first cited Rules, such as land count adjusted for ramp and average mana value, MDFC weighting, and Land Sources per color.
- Each Verdict in the response names its Rule.

### M3: React UI

- A React + TypeScript + Vite app in `frontend/`: paste a Deck List, view the Analysis, and chart the mana curve.
- The Wizards of the Coast Fan Content Policy notice, and card images shown unaltered ([ADR-0004](adr/0004-scryfall-data-use-constraints.md)).

### M4: Share Links and the Snapshot refresh

- Share Links that store the Deck List and re-run the Analysis ([ADR-0010](adr/0010-share-links-recompute.md)).
- A scheduled daily job that builds a new Snapshot and switches to it in one atomic step ([ADR-0003](adr/0003-versioned-local-scryfall-snapshots.md)).

### M5: Archidekt import

- A server-side importer for Archidekt deck URLs. Archidekt's API is unofficial and undocumented, so the importer must fail clearly when it breaks.

### M6: Launch

- Rate limiting per IP address.
- Choose a host and deploy (see open decisions below).

## Open decisions

- **Hosting**, to be decided at M6 or earlier if the API needs it. Requirements: a container for FastAPI, static hosting for React, managed Postgres with `pgvector`, and support for a scheduled daily job.
- **The LLM approach and model**, to be revisited at the start of phase 2 ([ADR-0012](adr/0012-llm-via-anthropic-sdk-tool-use.md)).
- **Exact Rule thresholds and MDFC weighting**, to be researched and cited during M2.

## Working agreement

The goal is for the developer to learn to build and maintain this app, not to receive a finished codebase. For each feature:

1. Claude explains the design and its tradeoffs.
2. We agree on the interface.
3. Claude writes the failing tests, or the developer does once comfortable.
4. The developer writes the implementation.
5. Claude reviews it.

Claude writes the boilerplate and glue: project configuration, CI, fixtures and tooling.

## External facts (checked 2026-10-27)

- Scryfall's bulk-data API offers gzipped JSON Lines only (`jsonl_download_uri`), including an `oracle_tags` file.
- Archidekt answers unauthenticated requests to `/api/decks/{id}/` but has no official API and blocks cross-origin browser requests.
- Moxfield's API access policy could not be confirmed.
