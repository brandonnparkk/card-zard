"""SQLAlchemy models for the `snapshots` and `cards` tables.

These classes describe database *tables*. They subclass our SQLAlchemy `Base`,
which is how Alembic finds them for autogenerate (env.py imports this module).
They are not Pydantic models: Pydantic schemas for API requests and responses
will live in the API package later, kept separate from these (ADR-0009).
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Float, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from card_zard.db import Base


class Snapshot(Base):
    """One recorded load of a Scryfall bulk file (ADR-0013).

    Card data itself lives in `cards` and is upserted in place; this table only
    remembers *which* load the current data came from, so every Analysis can
    record the Snapshot it ran against.
    """

    # Must match the table name the tests and the migration use.
    __tablename__ = "snapshots"

    # Pattern for every column:
    #   name: Mapped[<Python type>] = mapped_column(<database type>, ...)
    # `Mapped[str]` means NOT NULL; `Mapped[str | None]` would allow NULL.
    id: Mapped[int] = mapped_column(primary_key=True)

    version: Mapped[str] = mapped_column(Text)

    # timezone=True makes this `timestamptz`. Plain DateTime would drop the
    # timezone and hand back naive datetimes, which the tests reject.
    loaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    # The bulk file's name only (not the full path), e.g. "oracle-cards.jsonl".
    source_file: Mapped[str] = mapped_column(Text)

    # A SHA-256 hex digest is always exactly 64 characters. String(64) is
    # varchar(64), so a longer value is rejected instead of stored silently.
    # The loader compares this with the latest Snapshot to skip same-file reloads.
    source_sha256: Mapped[str] = mapped_column(String(64))


class Card(Base):
    """One Oracle card, as of the latest Snapshot (ADR-0013).

    Each load upserts rows by `oracle_id` and deletes cards missing from the
    new bulk file, so this table always mirrors the latest load. There is no
    link to `snapshots`: a card doesn't belong to a load, it's just current.

    Per-face fields are arrays with one entry per face, in Scryfall's order.
    Single-faced cards get one-element arrays, so code never has to check
    "does this card have faces?" before reading them.
    """

    __tablename__ = "cards"

    # `UUID` with no explicit column type: SQLAlchemy picks Postgres's native
    # uuid type (16 bytes, and Postgres rejects malformed values). The loader
    # must pass UUID(...) objects, not Scryfall's strings.
    oracle_id: Mapped[UUID] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(Text)

    # Scryfall's `cmc`. Not an int: some cards have half values (Little Girl
    # is 0.5), and an integer column would silently round them. Float (double
    # precision) stores halves exactly and comes back as a plain Python float,
    # which serializes to JSON cleanly (Numeric would give you Decimal).
    mana_value: Mapped[float] = mapped_column(Float)

    # e.g. "normal", "split", "transform". Text rather than an enum, because
    # Scryfall adds new layouts, and the loader is what skips non-game ones.
    layout: Mapped[str] = mapped_column(Text)

    # Scryfall's `legalities.commander`: "legal", "not_legal", "banned", ...
    commander_legality: Mapped[str] = mapped_column(Text)

    # TEXT[] columns. The tests check for exactly ARRAY(Text), which is why the
    # type is spelled out. No server default: the loader always supplies a
    # list, using [] when Scryfall omits the field (e.g. produced_mana).
    # Watch out: SQLAlchemy doesn't notice in-place changes like .append() on
    # a loaded row; assign a new list instead.
    face_names: Mapped[list[str]] = mapped_column(ARRAY(Text))
    type_lines: Mapped[list[str]] = mapped_column(ARRAY(Text))
    oracle_texts: Mapped[list[str]] = mapped_column(ARRAY(Text))
    color_identity: Mapped[list[str]] = mapped_column(ARRAY(Text))  # ["R", "U"]
    produced_mana: Mapped[list[str]] = mapped_column(ARRAY(Text))
    keywords: Mapped[list[str]] = mapped_column(ARRAY(Text))
