from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import ContextManager, Iterator

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS book_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    author TEXT NOT NULL,
    isbn TEXT,
    genre TEXT NOT NULL,
    book_details TEXT,
    publisher TEXT,
    publication_year INTEGER,
    edition TEXT,
    page_count INTEGER,
    srp_minor INTEGER,
    metadata_source TEXT,
    metadata_status TEXT NOT NULL DEFAULT 'Manual entry',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_book_records_isbn
    ON book_records(isbn) WHERE isbn IS NOT NULL AND trim(isbn) <> '';
CREATE INDEX IF NOT EXISTS ix_book_records_title ON book_records(title COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS ix_book_records_author ON book_records(author COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS ix_book_records_genre ON book_records(genre);

CREATE TABLE IF NOT EXISTS copies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    copy_code TEXT UNIQUE,
    book_id INTEGER NOT NULL REFERENCES book_records(id) ON DELETE RESTRICT,
    copy_number INTEGER NOT NULL,
    format TEXT NOT NULL,
    condition TEXT NOT NULL,
    location TEXT NOT NULL DEFAULT 'Not Specified',
    photo_path TEXT NOT NULL,
    price_minor INTEGER NOT NULL CHECK(price_minor > 0),
    status TEXT NOT NULL DEFAULT 'Available'
        CHECK(status IN ('Available','Not for Sale','Listed','Sold')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE(book_id, copy_number)
);
CREATE INDEX IF NOT EXISTS ix_copies_book_id ON copies(book_id);
CREATE INDEX IF NOT EXISTS ix_copies_status ON copies(status);
CREATE INDEX IF NOT EXISTS ix_copies_location ON copies(location COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS ix_copies_price ON copies(price_minor);

CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    copy_id INTEGER NOT NULL REFERENCES copies(id) ON DELETE RESTRICT,
    actual_sale_price_minor INTEGER NOT NULL CHECK(actual_sale_price_minor > 0),
    sale_date TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE(copy_id)
);

CREATE TABLE IF NOT EXISTS app_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
PRAGMA user_version = 1;
"""


class Database:
    """Small SQLite boundary with foreign keys and explicit transactions."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """Yield a configured connection and always close it after the transaction."""
        conn = sqlite3.connect(self.path, timeout=15)
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA busy_timeout = 15000")
            with conn:
                yield conn
        finally:
            conn.close()

    def _initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)
            conn.execute("INSERT OR IGNORE INTO app_meta(key, value) VALUES('schema_version', ?)", (str(SCHEMA_VERSION),))

    def transaction(self) -> ContextManager[sqlite3.Connection]:
        """Return a connection context manager; sqlite commits/rolls back on exit."""
        return self.connect()

    def backup_to(self, destination: str | Path) -> Path:
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        target = sqlite3.connect(destination)
        try:
            with self.connect() as source:
                source.backup(target)
            target.execute("PRAGMA integrity_check")
            target.commit()
        finally:
            target.close()
        return destination

    def integrity_check(self) -> tuple[bool, str]:
        with self.connect() as conn:
            row = conn.execute("PRAGMA integrity_check").fetchone()
            message = str(row[0]) if row else "No result"
            return message.lower() == "ok", message
