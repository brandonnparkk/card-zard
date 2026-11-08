# Card data is upserted in place on each load; old card data lives only in backups

This partly supersedes ADR-0003, which kept a full copy of card data for each Snapshot and switched between copies in one atomic step. Instead, one `cards` table is upserted in place on each load, deleting Cards missing from the loaded file, and a `snapshots` table gets one row per load with its version identifier, the time it was loaded, and the source file's name and hash. Each load runs in one database transaction, so readers see either all of the old card data or all of the new, never a mix; this replaces the separate atomic switch. Every Analysis and Share Link still records the Snapshot it ran against, so every Analysis is still produced against exactly one Snapshot. Old card data is not kept in the database: the only history is the nightly database backups. We chose this because a Snapshot is about 39,300 Cards, so a full copy each day adds about 14 million rows a year unless something prunes them, and nothing planned (issues #3–#9 and the roadmap) reads old card data. One table keeps the schema and queries simpler and needs no retention job.

The rest of ADR-0003 still stands: card data comes from local bulk files and never from the live Scryfall API, a new Snapshot is built each day, and every Analysis records its Snapshot.

## Consequences

- A Snapshot's version identifier records when and from which file card data was loaded. It can't be used to read that data back; an old Snapshot's Cards can only be recovered by restoring a backup.
- A Share Link can say that it was first analyzed against one Snapshot and is now analyzed against another, but it can't show which Cards changed in between. This drops ADR-0010's promise to explain why its Verdicts changed.
- Hosting must provide nightly database backups.

## Considered Options

- **A full copy of card data per Snapshot** (ADR-0003's original approach): makes every past Analysis reproducible, but grows by about 14 million rows a year and needs a retention job, all for history that nothing planned reads.
- **A `card_changes` table** holding the old values of only the Cards that changed in each load: deferred. It would let a Share Link show which Cards changed between Snapshots, and it can be added later without changing the `cards` table.
