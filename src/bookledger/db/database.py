from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import ContextManager, Iterator

SCHEMA_VERSION = 7

_DATABASE_LOCKS: dict[str, threading.RLock] = {}
_DATABASE_LOCKS_GUARD = threading.Lock()

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
    copy_uuid TEXT NOT NULL UNIQUE,
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
CREATE TABLE IF NOT EXISTS trash_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    copy_id INTEGER NOT NULL UNIQUE REFERENCES copies(id) ON DELETE RESTRICT,
    deleted_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    original_status TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS storage_operations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    operation TEXT NOT NULL,
    copy_id INTEGER,
    source_path TEXT,
    target_path TEXT,
    backup_path TEXT,
    state TEXT NOT NULL DEFAULT 'prepared',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE TABLE IF NOT EXISTS locations (
    name TEXT PRIMARY KEY COLLATE NOCASE
);
CREATE INDEX IF NOT EXISTS ix_copies_book_id ON copies(book_id);
CREATE INDEX IF NOT EXISTS ix_copies_status ON copies(status);
CREATE INDEX IF NOT EXISTS ix_copies_location ON copies(location COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS ix_copies_price ON copies(price_minor);
CREATE TRIGGER IF NOT EXISTS copies_copy_uuid_immutable
    BEFORE UPDATE OF copy_uuid ON copies
    WHEN OLD.copy_uuid IS NOT NULL AND NEW.copy_uuid IS NOT OLD.copy_uuid
    BEGIN SELECT RAISE(ABORT, 'copy UUID is immutable'); END;

CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    copy_id INTEGER NOT NULL REFERENCES copies(id) ON DELETE RESTRICT,
    price_minor INTEGER NOT NULL CHECK(price_minor > 0),
    sale_date TEXT NOT NULL,
    voided_at TEXT,
    void_reason TEXT CHECK(void_reason IS NULL OR void_reason IN (
        'Marked Sold by Mistake','Cancelled Order','Returned Order','Test'
    )),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE INDEX IF NOT EXISTS ix_sales_copy_id ON sales(copy_id, id);
CREATE UNIQUE INDEX IF NOT EXISTS ux_sales_one_active_copy
    ON sales(copy_id) WHERE voided_at IS NULL;

CREATE TABLE IF NOT EXISTS app_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
PRAGMA user_version = 7;
"""


class Database:
    """Small SQLite boundary with foreign keys and explicit transactions."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock_key = str(self.path.resolve()).casefold()
        with _DATABASE_LOCKS_GUARD:
            self._operation_lock = _DATABASE_LOCKS.setdefault(lock_key, threading.RLock())
        self._initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """Yield a configured connection and always close it after the transaction."""
        with self._operation_lock:
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
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            if version == 1:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute("CREATE TABLE locations (name TEXT PRIMARY KEY COLLATE NOCASE)")
                conn.execute("INSERT OR IGNORE INTO locations(name) VALUES('Not Specified')")
                conn.execute("INSERT OR IGNORE INTO locations(name) SELECT DISTINCT trim(location) FROM copies WHERE trim(location) <> ''")
                conn.execute("UPDATE copies SET location='Not Specified' WHERE trim(location) = ''")
                for row in conn.execute("SELECT DISTINCT location FROM copies").fetchall():
                    canonical = conn.execute("SELECT name FROM locations WHERE name=? COLLATE NOCASE", (str(row[0]).strip(),)).fetchone()
                    if canonical:
                        conn.execute("UPDATE copies SET location=? WHERE trim(location)=? COLLATE NOCASE", (canonical[0], str(row[0]).strip()))
                conn.execute("PRAGMA user_version = 2")
                conn.commit()
                version = 2
            if version == 2:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute("""CREATE TABLE sales_v3 (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    copy_id INTEGER NOT NULL REFERENCES copies(id) ON DELETE RESTRICT,
                    price_minor INTEGER NOT NULL CHECK(price_minor > 0),
                    sale_date TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
                )""")
                conn.execute("INSERT INTO sales_v3(id,copy_id,price_minor,sale_date,created_at) SELECT id,copy_id,actual_sale_price_minor,sale_date,created_at FROM sales")
                conn.execute("DROP TABLE sales")
                conn.execute("ALTER TABLE sales_v3 RENAME TO sales")
                conn.execute("CREATE INDEX ix_sales_copy_id ON sales(copy_id, id)")
                conn.execute("PRAGMA user_version = 3")
                conn.commit()
                version = 3
            if version == 3:
                # Rebuild legacy copies only here: old files may lack AUTOINCREMENT
                # and the book foreign key. Explicit IDs/codes are copied verbatim.
                # The child sales table keeps its table-name reference while the
                # parent is replaced, with enforcement checked after the migration.
                conn.execute("PRAGMA foreign_keys = OFF")
                try:
                    conn.execute("BEGIN IMMEDIATE")
                    conn.execute("""CREATE TABLE copies_v4 (
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
                    )""")
                    conn.execute("""INSERT INTO copies_v4(
                        id,copy_code,book_id,copy_number,format,condition,location,photo_path,
                        price_minor,status,created_at,updated_at
                    ) SELECT id,copy_code,book_id,copy_number,format,condition,location,photo_path,
                             price_minor,status,created_at,updated_at FROM copies""")
                    conn.execute("DROP TABLE copies")
                    conn.execute("ALTER TABLE copies_v4 RENAME TO copies")
                    conn.execute("CREATE INDEX ix_copies_book_id ON copies(book_id)")
                    conn.execute("CREATE INDEX ix_copies_status ON copies(status)")
                    conn.execute("CREATE INDEX ix_copies_location ON copies(location COLLATE NOCASE)")
                    conn.execute("CREATE INDEX ix_copies_price ON copies(price_minor)")
                    conn.execute("""CREATE TABLE trash_entries (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        copy_id INTEGER NOT NULL UNIQUE REFERENCES copies(id) ON DELETE RESTRICT,
                        deleted_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
                        original_status TEXT NOT NULL
                    )""")
                    conn.execute("""CREATE TABLE storage_operations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        operation TEXT NOT NULL,
                        copy_id INTEGER,
                        source_path TEXT,
                        target_path TEXT,
                        backup_path TEXT,
                        state TEXT NOT NULL DEFAULT 'prepared',
                        created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
                    )""")
                    conn.execute("PRAGMA user_version = 4")
                    conn.commit()
                    version = 4
                except Exception:
                    conn.rollback()
                    raise
                finally:
                    conn.execute("PRAGMA foreign_keys = ON")
            if version == 4:
                # Existing records cannot distinguish a completed sale from a
                # status reversal. Reconcile the active row against current copy
                # status while preserving every original sale value and ID.
                conn.execute("BEGIN IMMEDIATE")
                try:
                    conn.execute("ALTER TABLE sales ADD COLUMN voided_at TEXT")
                    conn.execute(
                        """UPDATE sales SET voided_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
                           WHERE NOT EXISTS (
                               SELECT 1 FROM copies c WHERE c.id=sales.copy_id AND c.status='Sold'
                                 AND sales.id=(SELECT MAX(s2.id) FROM sales s2 WHERE s2.copy_id=sales.copy_id)
                           )"""
                    )
                    conn.execute(
                        "CREATE UNIQUE INDEX ux_sales_one_active_copy ON sales(copy_id) WHERE voided_at IS NULL"
                    )
                    conn.execute("PRAGMA user_version = 5")
                    conn.commit()
                    version = 5
                except Exception:
                    conn.rollback()
                    raise
            if version == 5:
                conn.execute("BEGIN IMMEDIATE")
                try:
                    conn.execute("""ALTER TABLE sales ADD COLUMN void_reason TEXT
                        CHECK(void_reason IS NULL OR void_reason IN (
                            'Marked Sold by Mistake','Cancelled Order','Returned Order','Test'
                        ))""")
                    conn.execute("PRAGMA user_version = 6")
                    conn.commit()
                    version = 6
                except Exception:
                    conn.rollback()
                    raise
            if version == 6:
                import uuid

                conn.execute("BEGIN IMMEDIATE")
                try:
                    conn.execute("ALTER TABLE copies ADD COLUMN copy_uuid TEXT")
                    for row in conn.execute("SELECT id FROM copies WHERE copy_uuid IS NULL").fetchall():
                        conn.execute("UPDATE copies SET copy_uuid=? WHERE id=?", (str(uuid.uuid4()), row[0]))
                    conn.execute("CREATE UNIQUE INDEX ux_copies_copy_uuid ON copies(copy_uuid)")
                    conn.execute("DROP TRIGGER IF EXISTS copies_copy_uuid_immutable")
                    conn.execute("""CREATE TRIGGER copies_copy_uuid_immutable
                        BEFORE UPDATE OF copy_uuid ON copies
                        WHEN OLD.copy_uuid IS NOT NULL AND NEW.copy_uuid IS NOT OLD.copy_uuid
                        BEGIN SELECT RAISE(ABORT, 'copy UUID is immutable'); END""")
                    conn.execute("""CREATE TRIGGER copies_copy_uuid_required
                        BEFORE INSERT ON copies WHEN NEW.copy_uuid IS NULL OR trim(NEW.copy_uuid)=''
                        BEGIN SELECT RAISE(ABORT, 'copy UUID is required'); END""")
                    conn.execute("PRAGMA user_version = 7")
                    conn.commit()
                    version = 7
                except Exception:
                    conn.rollback()
                    raise
            conn.executescript(SCHEMA)
            conn.execute("INSERT INTO app_meta(key, value) VALUES('schema_version', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(SCHEMA_VERSION),))
            conn.execute("INSERT OR IGNORE INTO locations(name) VALUES('Not Specified')")

    def transaction(self) -> ContextManager[sqlite3.Connection]:
        """Return a connection context manager; sqlite commits/rolls back on exit."""
        return self.connect()

    @contextmanager
    def operation_guard(self) -> Iterator[None]:
        """Exclude all database connections in this process during a library operation."""
        with self._operation_lock:
            yield

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
