---
status: partly superseded by ADR-0013
---

# Card data comes from versioned local Scryfall Snapshots, not the live API

All card lookups read from a local Snapshot built from Scryfall's `oracle_cards` and `oracle_tags` bulk files, never from the live Scryfall API at request time. A scheduled job builds a new Snapshot each day and switches to it in one atomic step, and every Analysis records the Snapshot it used. We chose this because Scryfall asks clients to use bulk data instead of heavy API traffic, a 100-card deck would otherwise need about 100 lookups per request, and recording the Snapshot makes "why did my Analysis change?" answerable.

How Snapshots are stored, including the atomic switch, is superseded by ADR-0013: card data is upserted in place in one transaction, and only the latest Snapshot's card data is kept.

## Consequences

- Scryfall's bulk files are gzipped JSON Lines only (`jsonl_download_uri`), confirmed on 2026-10-27.
- Newly spoiled cards appear only after the next Snapshot, so up to a day late.
