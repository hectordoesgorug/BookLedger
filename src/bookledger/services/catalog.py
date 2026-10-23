from __future__ import annotations
from datetime import date
import json
import math
from pathlib import Path
import sqlite3
import uuid
from bookledger.config import APPROVED_GENRES, COPY_STATUSES, DEFAULT_FORMATS, DEFAULT_LOCATION
from bookledger.db.database import Database
from bookledger.services.isbn import isbn_check, normalize_isbn
from bookledger.services.photos import PhotoService

REQUIRED_COPY_FIELDS = ("title", "author", "genre", "format", "condition", "price", "photo_path")
MAX_MONEY_MINOR = 2**63 - 1
SALE_VOID_REASONS = (
    "Marked Sold by Mistake",
    "Cancelled Order",
    "Returned Order",
    "Test",
)

_CONFIGURABLE_LISTS = {
    "genre": ("genre_options", "book_records", "genre", APPROVED_GENRES),
    "format": ("format_options", "copies", "format", DEFAULT_FORMATS),
}


class ValidationError(ValueError):
    def __init__(self, errors: dict[str, str]):
        self.errors = errors
        super().__init__("The form contains invalid or missing fields.")


class CatalogService:
    def __init__(self, db: Database, data_dir: str | Path | None = None, *, config_store=None):
        self.db = db
        self.data_dir = Path(data_dir) if data_dir else db.path.parent
        self.photos = PhotoService(self.data_dir / "photos", self.data_dir / "trash")
        self.config_store = config_store

    @staticmethod
    def _preference_key(kind: str) -> str:
        return {"genre": "genres", "format": "formats", "location": "locations"}[kind]

    def _legacy_configurable_values(self, conn, kind: str) -> list[str]:
        key, table, column, defaults = _CONFIGURABLE_LISTS[kind]
        row = conn.execute("SELECT value FROM app_meta WHERE key=?", (key,)).fetchone()
        try:
            stored = json.loads(row[0]) if row else defaults
        except (ValueError, TypeError):
            stored = defaults
        values = []
        seen = set()
        for raw in stored if isinstance(stored, list) else defaults:
            value = str(raw or "").strip()
            if value and value.casefold() not in seen:
                values.append(value)
                seen.add(value.casefold())
        for assigned in conn.execute(
            f"SELECT DISTINCT trim({column}) FROM {table} WHERE trim({column})<>'' ORDER BY trim({column}) COLLATE NOCASE"
        ):
            value = str(assigned[0]).strip()
            if value.casefold() not in seen:
                values.append(value)
                seen.add(value.casefold())
        return values

    def _configurable_values(self, conn, kind: str) -> list[str]:
        if self.config_store is not None:
            configured = self.config_store.get(("preferences", self._preference_key(kind)), None)
            if isinstance(configured, list) and all(isinstance(value, str) for value in configured):
                return list(configured)
            return self._legacy_configurable_values(conn, kind)
        try:
            key, table, column, defaults = _CONFIGURABLE_LISTS[kind]
        except KeyError as exc:
            raise ValueError(f"Unsupported configurable list: {kind}") from exc
        row = conn.execute("SELECT value FROM app_meta WHERE key=?", (key,)).fetchone()
        try:
            stored = json.loads(row[0]) if row else defaults
        except (ValueError, TypeError):
            stored = defaults
        values = []
        seen = set()
        for raw in stored if isinstance(stored, list) else defaults:
            value = str(raw or "").strip()
            folded = value.casefold()
            if value and folded not in seen:
                values.append(value)
                seen.add(folded)
        # Preserve pre-existing assignments that are outside today's built-in
        # options. This is a data-preserving compatibility seed, not a rewrite.
        for assigned in conn.execute(
            f"SELECT DISTINCT trim({column}) FROM {table} WHERE trim({column})<>'' ORDER BY trim({column}) COLLATE NOCASE"
        ):
            value = str(assigned[0]).strip()
            if value.casefold() not in seen:
                values.append(value)
                seen.add(value.casefold())
        encoded = json.dumps(values, ensure_ascii=False)
        if not row or row[0] != encoded:
            conn.execute(
                "INSERT INTO app_meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, encoded),
            )
        return values

    def list_configurable_values(self, kind: str) -> tuple[str, ...]:
        if self.config_store is not None:
            with self.db.connect() as conn:
                return tuple(self._configurable_values(conn, kind))
        with self.db.connect() as conn:
            return tuple(self._configurable_values(conn, kind))

    def list_genres(self) -> tuple[str, ...]:
        return self.list_configurable_values("genre")

    def list_formats(self) -> tuple[str, ...]:
        return self.list_configurable_values("format")

    def value_assignment_count(self, kind: str, value: str) -> int:
        try:
            _key, table, column, _defaults = _CONFIGURABLE_LISTS[kind]
        except KeyError as exc:
            raise ValueError(f"Unsupported configurable list: {kind}") from exc
        with self.db.connect() as conn:
            return int(conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE {column}=? COLLATE NOCASE", (value,)
            ).fetchone()[0])

    def _save_configurable_values(self, conn, kind: str, values: list[str]) -> None:
        key = _CONFIGURABLE_LISTS[kind][0]
        conn.execute(
            "INSERT INTO app_meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, json.dumps(values, ensure_ascii=False)),
        )

    def add_configurable_value(self, kind: str, name: str) -> str:
        name = (name or "").strip()
        if not name:
            raise ValidationError({kind: f"{kind.title()} name is required."})
        if self.config_store is not None:
            key = self._preference_key(kind)
            values = list(self.list_configurable_values(kind))
            if any(value.casefold() == name.casefold() for value in values):
                raise ValidationError({kind: f"A {kind} with this name already exists."})
            self.config_store.set(("preferences", key), values + [name])
            return name
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            values = self._configurable_values(conn, kind)
            if any(value.casefold() == name.casefold() for value in values):
                raise ValidationError({kind: f"A {kind} with this name already exists."})
            values.append(name)
            self._save_configurable_values(conn, kind, values)
        return name

    def rename_configurable_value(self, kind: str, current: str, replacement: str) -> str:
        replacement = (replacement or "").strip()
        if not replacement:
            raise ValidationError({kind: f"{kind.title()} name is required."})
        try:
            _key, table, column, _defaults = _CONFIGURABLE_LISTS[kind]
        except KeyError as exc:
            raise ValueError(f"Unsupported configurable list: {kind}") from exc
        if self.config_store is not None:
            key = self._preference_key(kind)
            old_values = list(self.list_configurable_values(kind))
            actual = next((value for value in old_values if value.casefold() == current.casefold()), None)
            if actual is None:
                raise ValidationError({kind: f"Choose an existing {kind}."})
            if replacement.casefold() != actual.casefold() and any(
                value.casefold() == replacement.casefold() for value in old_values
            ):
                raise ValidationError({kind: f"A {kind} with this name already exists."})
            new_values = list(old_values)
            new_values[new_values.index(actual)] = replacement
            wrote_config = False
            try:
                with self.db.connect() as conn:
                    conn.execute("BEGIN IMMEDIATE")
                    conn.execute(
                        f"UPDATE {table} SET {column}=? WHERE {column}=? COLLATE NOCASE",
                        (replacement, actual),
                    )
                    self.config_store.set(("preferences", key), new_values)
                    wrote_config = True
            except Exception as exc:
                if wrote_config:
                    try:
                        self.config_store.set(("preferences", key), old_values)
                    except Exception as rollback_exc:
                        raise RuntimeError(
                            f"The {kind} rename could not be fully rolled back; configuration recovery is required."
                        ) from rollback_exc
                raise exc
            return replacement
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            values = self._configurable_values(conn, kind)
            actual = next((value for value in values if value.casefold() == current.casefold()), None)
            if actual is None:
                raise ValidationError({kind: f"Choose an existing {kind}."})
            if replacement.casefold() != actual.casefold() and any(
                value.casefold() == replacement.casefold() for value in values
            ):
                raise ValidationError({kind: f"A {kind} with this name already exists."})
            conn.execute(
                f"UPDATE {table} SET {column}=? WHERE {column}=? COLLATE NOCASE",
                (replacement, actual),
            )
            values[values.index(actual)] = replacement
            self._save_configurable_values(conn, kind, values)
        return replacement

    def delete_configurable_value(self, kind: str, name: str) -> None:
        try:
            _key, table, column, _defaults = _CONFIGURABLE_LISTS[kind]
        except KeyError as exc:
            raise ValueError(f"Unsupported configurable list: {kind}") from exc
        if self.config_store is not None:
            key = self._preference_key(kind)
            with self.db.connect() as conn:
                conn.execute("BEGIN IMMEDIATE")
                values = list(self.list_configurable_values(kind))
                actual = next((value for value in values if value.casefold() == name.casefold()), None)
                if actual is None:
                    raise ValidationError({kind: f"Choose an existing {kind}."})
                if conn.execute(
                    f"SELECT 1 FROM {table} WHERE {column}=? COLLATE NOCASE LIMIT 1", (actual,)
                ).fetchone():
                    raise ValidationError({kind: f"This {kind} is assigned to one or more books."})
                values.remove(actual)
                self.config_store.set(("preferences", key), values)
            return
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            values = self._configurable_values(conn, kind)
            actual = next((value for value in values if value.casefold() == name.casefold()), None)
            if actual is None:
                raise ValidationError({kind: f"Choose an existing {kind}."})
            if conn.execute(
                f"SELECT 1 FROM {table} WHERE {column}=? COLLATE NOCASE LIMIT 1", (actual,)
            ).fetchone():
                raise ValidationError({kind: f"This {kind} is assigned to one or more books."})
            values.remove(actual)
            self._save_configurable_values(conn, kind, values)

    def add_genre(self, name: str) -> str:
        return self.add_configurable_value("genre", name)

    def rename_genre(self, current: str, replacement: str) -> str:
        return self.rename_configurable_value("genre", current, replacement)

    def delete_genre(self, name: str) -> None:
        self.delete_configurable_value("genre", name)

    def add_format(self, name: str) -> str:
        return self.add_configurable_value("format", name)

    def rename_format(self, current: str, replacement: str) -> str:
        return self.rename_configurable_value("format", current, replacement)

    def delete_format(self, name: str) -> None:
        self.delete_configurable_value("format", name)

    def _resolve_photo(self, value: str | Path) -> Path:
        path = Path(value)
        return path if path.is_absolute() else self.data_dir / path

    def _stored_photo_path(self, value: str | Path) -> str:
        path = self._resolve_photo(value).resolve()
        try:
            return path.relative_to(self.data_dir.resolve()).as_posix()
        except ValueError:
            # Intake normally stages photos inside the portable data folder. Rejecting
            # outside paths avoids silently creating a non-portable catalog reference.
            raise ValidationError({"photo_path": "The photo must be stored in the BookLedger data folder."})

    def validate(self, payload: dict, *, isbn_override: bool = False, conn=None) -> dict[str, str]:
        errors: dict[str, str] = {}
        for field in ("title", "author", "genre", "format", "condition", "photo_path"):
            if not str(payload.get(field) or "").strip():
                errors[field] = {
                    "title": "Title is required.",
                    "author": "Author is required.",
                    "genre": "Genre is required.",
                    "format": "Format is required.",
                    "condition": "Condition is required.",
                    "photo_path": "A copy photo is required.",
                }[field]
        genre = str(payload.get("genre") or "").strip()
        format_name = str(payload.get("format") or "").strip()
        genres = self._configurable_values(conn, "genre") if conn is not None else self.list_genres()
        formats = self._configurable_values(conn, "format") if conn is not None else self.list_formats()
        if genre and genre not in genres:
            errors["genre"] = "Choose one of the approved genres."
        if format_name and format_name not in formats:
            errors["format"] = "Choose one of the approved formats."
        try:
            price = float(str(payload.get("price") or "").replace(",", ""))
            scaled_price = price * 100
            if not math.isfinite(price) or price <= 0 or not math.isfinite(scaled_price) or scaled_price > MAX_MONEY_MINOR:
                errors["price"] = "Enter a valid price greater than PHP 0."
        except (TypeError, ValueError):
            errors["price"] = "Enter a valid price greater than PHP 0."
        photo = str(payload.get("photo_path") or "").strip()
        if photo:
            resolved = self._resolve_photo(photo)
            if not resolved.is_file() or resolved.stat().st_size <= 0:
                errors["photo_path"] = "Choose a photo that can be saved."
            else:
                try:
                    resolved.resolve().relative_to(self.data_dir.resolve())
                except ValueError:
                    errors["photo_path"] = "The photo must be stored in the BookLedger data folder."
        isbn = normalize_isbn(payload.get("isbn"))
        if isbn:
            valid, message = isbn_check(isbn)
            if not valid and not isbn_override:
                errors["isbn"] = message + " Select the manual override to continue anyway."
        return errors

    def duplicate_by_isbn(self, isbn: str | None):
        isbn = normalize_isbn(isbn)
        if not isbn:
            return None
        with self.db.connect() as conn:
            return conn.execute("SELECT * FROM book_records WHERE isbn = ?", (isbn,)).fetchone()

    def no_isbn_title_author_matches(self, title: str, author: str):
        with self.db.connect() as conn:
            return conn.execute(
                "SELECT * FROM book_records WHERE (isbn IS NULL OR trim(isbn)='') AND title=? COLLATE NOCASE AND author=? COLLATE NOCASE ORDER BY id",
                (title.strip(), author.strip()),
            ).fetchall()

    def list_locations(self) -> tuple[str, ...]:
        if self.config_store is not None:
            with self.db.connect() as conn:
                values = self.config_store.get(("preferences", "locations"), None)
                if isinstance(values, list) and all(isinstance(value, str) for value in values):
                    return tuple(values)
                assigned = conn.execute(
                    "SELECT DISTINCT trim(location) FROM copies WHERE trim(location)<>'' ORDER BY trim(location) COLLATE NOCASE"
                ).fetchall()
                return tuple(self._append_values((), assigned))
        with self.db.connect() as conn:
            return tuple(row[0] for row in conn.execute("SELECT name FROM locations ORDER BY name COLLATE NOCASE"))

    @staticmethod
    def _append_values(values, assigned) -> list[str]:
        result = list(values)
        seen = {value.casefold() for value in result}
        for row in assigned:
            value = str(row[0] or "").strip()
            if value and value.casefold() not in seen:
                result.append(value)
                seen.add(value.casefold())
        return result

    def location_assignment_count(self, name: str) -> int:
        with self.db.connect() as conn:
            return int(conn.execute(
                "SELECT COUNT(*) FROM copies WHERE location=? COLLATE NOCASE", (name,)
            ).fetchone()[0])

    def add_location(self, name: str) -> str:
        name = (name or "").strip()
        if not name:
            raise ValidationError({"location": "Location name is required."})
        if self.config_store is not None:
            values = list(self.list_locations())
            if any(value.casefold() == name.casefold() for value in values):
                raise ValidationError({"location": "A location with this name already exists."})
            self.config_store.set(("preferences", "locations"), values + [name])
            return name
        try:
            with self.db.connect() as conn:
                conn.execute("INSERT INTO locations(name) VALUES(?)", (name,))
        except sqlite3.IntegrityError as exc:
            raise ValidationError({"location": "A location with this name already exists."}) from exc
        return name

    def rename_location(self, current: str, replacement: str) -> str:
        replacement = (replacement or "").strip()
        if not replacement:
            raise ValidationError({"location": "Location name is required."})
        if current.casefold() == DEFAULT_LOCATION.casefold() and replacement.casefold() != DEFAULT_LOCATION.casefold():
            raise ValidationError({"location": "The default location cannot be renamed."})
        if self.config_store is not None:
            old_values = list(self.list_locations())
            actual = next((value for value in old_values if value.casefold() == current.casefold()), None)
            if actual is None:
                raise ValidationError({"location": "Choose an existing location."})
            if actual.casefold() != replacement.casefold() and any(
                value.casefold() == replacement.casefold() for value in old_values
            ):
                raise ValidationError({"location": "A location with this name already exists."})
            new_values = list(old_values)
            new_values[new_values.index(actual)] = replacement
            wrote_config = False
            try:
                with self.db.connect() as conn:
                    conn.execute("BEGIN IMMEDIATE")
                    conn.execute("UPDATE copies SET location=? WHERE location=? COLLATE NOCASE", (replacement, actual))
                    self.config_store.set(("preferences", "locations"), new_values)
                    wrote_config = True
            except Exception as exc:
                if wrote_config:
                    try:
                        self.config_store.set(("preferences", "locations"), old_values)
                    except Exception as rollback_exc:
                        raise RuntimeError("The Location rename could not be fully rolled back; configuration recovery is required.") from rollback_exc
                raise exc
            return replacement
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if not conn.execute("SELECT 1 FROM locations WHERE name=? COLLATE NOCASE", (current,)).fetchone():
                raise ValidationError({"location": "Choose an existing location."})
            if current.casefold() != replacement.casefold() and conn.execute(
                "SELECT 1 FROM locations WHERE name=? COLLATE NOCASE", (replacement,)
            ).fetchone():
                raise ValidationError({"location": "A location with this name already exists."})
            conn.execute("UPDATE locations SET name=? WHERE name=? COLLATE NOCASE", (replacement, current))
            conn.execute("UPDATE copies SET location=? WHERE location=? COLLATE NOCASE", (replacement, current))
        return replacement

    def delete_location(self, name: str) -> None:
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if name.casefold() == DEFAULT_LOCATION.casefold():
                raise ValidationError({"location": "The default location cannot be deleted."})
            if conn.execute("SELECT 1 FROM copies WHERE location=? COLLATE NOCASE LIMIT 1", (name,)).fetchone():
                raise ValidationError({"location": "This location is assigned to one or more copies."})
            if self.config_store is not None:
                values = list(self.list_locations())
                actual = next((value for value in values if value.casefold() == name.casefold()), None)
                if actual is None:
                    raise ValidationError({"location": "Choose an existing location."})
                values.remove(actual)
                self.config_store.set(("preferences", "locations"), values)
                return
            conn.execute("DELETE FROM locations WHERE name=? COLLATE NOCASE", (name,))

    def _canonical_location(self, conn, value: str | None) -> str:
        name = (value or "").strip() or DEFAULT_LOCATION
        if self.config_store is not None:
            row = next((item for item in self.list_locations() if item.casefold() == name.casefold()), None)
            if row is None:
                raise ValidationError({"location": "Choose a location from the approved location list."})
            return row
        row = conn.execute("SELECT name FROM locations WHERE name=? COLLATE NOCASE", (name,)).fetchone()
        if not row:
            raise ValidationError({"location": "Choose a location from the approved location list."})
        return row[0]

    def create_copy(self, payload: dict, *, isbn_override: bool = False, existing_book_id: int | None = None) -> int:
        errors = self.validate(payload, isbn_override=isbn_override)
        if errors:
            raise ValidationError(errors)
        price_minor = int(round(float(str(payload["price"]).replace(",", "")) * 100))
        srp_value = payload.get("srp")
        srp_minor = int(round(float(srp_value) * 100)) if srp_value not in (None, "") else None
        isbn = normalize_isbn(payload.get("isbn"))
        selected_photo = self._resolve_photo(payload["photo_path"])
        try:
            selected_photo.resolve().relative_to(self.photos.staging_dir.resolve())
            staged_photo = selected_photo
        except ValueError:
            try:
                staged_photo = self.photos.import_and_compress(selected_photo)
            except ValueError as exc:
                raise ValidationError({"photo_path": str(exc)}) from exc
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            errors = self.validate(payload, isbn_override=isbn_override, conn=conn)
            if errors:
                raise ValidationError(errors)
            book_id = existing_book_id
            if book_id is not None:
                existing = conn.execute("SELECT id,isbn FROM book_records WHERE id=?", (book_id,)).fetchone()
                if not existing:
                    raise ValidationError({"isbn": "The selected bibliographic record no longer exists. Refresh and try again."})
                stored_isbn = normalize_isbn(existing["isbn"])
                if isbn and stored_isbn != isbn:
                    raise ValidationError({"isbn": "The selected record does not match this ISBN."})
                if not isbn and stored_isbn:
                    raise ValidationError({"isbn": "Choose a matching no-ISBN record or enter the correct ISBN."})
            if book_id is None and isbn:
                row = conn.execute("SELECT id FROM book_records WHERE isbn=?", (isbn,)).fetchone()
                if row:
                    raise ValidationError({"isbn": "This ISBN already has a bibliographic record. Confirm adding another copy and reuse that record."})
            if book_id is None:
                try:
                    cur = conn.execute(
                        """INSERT INTO book_records(title,author,isbn,genre,book_details,publisher,publication_year,edition,page_count,srp_minor,metadata_source,metadata_status)
                           VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (payload["title"].strip(), payload["author"].strip(), isbn, payload["genre"],
                         (payload.get("book_details") or "").strip() or None,
                         (payload.get("publisher") or "").strip() or None,
                         int(payload["publication_year"]) if str(payload.get("publication_year") or "").isdigit() else None,
                         (payload.get("edition") or "").strip() or None,
                         int(payload["page_count"]) if str(payload.get("page_count") or "").isdigit() else None,
                         srp_minor, payload.get("metadata_source"), payload.get("metadata_status", "Manual entry")),
                    )
                except sqlite3.IntegrityError as exc:
                    raise ValidationError({"isbn": "A record with this ISBN already exists. Review the duplicate before saving."}) from exc
                book_id = int(cur.lastrowid)
            next_number = conn.execute("SELECT COALESCE(MAX(copy_number),0)+1 FROM copies WHERE book_id=?", (book_id,)).fetchone()[0]
            location = self._canonical_location(conn, payload.get("location"))
            cur = conn.execute(
                """INSERT INTO copies(copy_uuid,book_id,copy_number,format,condition,location,photo_path,price_minor,status)
                   VALUES(?,?,?,?,?,?,?,?,?)""",
                (str(uuid.uuid4()), book_id, next_number, payload["format"].strip(), payload["condition"].strip(), location,
                 "photos/pending.jpg", price_minor, "Available"),
            )
            copy_id = int(cur.lastrowid)
            code = f"BL-{copy_id:06d}"
            conn.execute("UPDATE copies SET copy_code=? WHERE id=?", (code, copy_id))
            conn.execute("UPDATE copies SET photo_path=? WHERE id=?", (f"photos/{copy_id}.jpg", copy_id))
            conn.execute("INSERT INTO storage_operations(operation,copy_id,source_path,target_path,state) VALUES('install',?,?,?,'prepared')",
                         (copy_id, staged_photo.resolve().relative_to(self.data_dir.resolve()).as_posix(), f"photos/{copy_id}.jpg"))
            conn.commit()
        try:
            self.photos.install(copy_id, staged_photo)
            with self.db.connect() as conn:
                conn.execute("DELETE FROM storage_operations WHERE operation='install' AND copy_id=?", (copy_id,))
            return copy_id
        except Exception:
            # Keep the durable pending operation so verification can diagnose and
            # retry recovery; ordinary views exclude copies with pending operations.
            raise ValidationError({"photo_path": f"Photo installation needs recovery: {staged_photo}"})

    def list_copies(
        self,
        search: str = "",
        status: str = "All",
        genre: str = "All",
        condition: str = "All",
        location: str = "All",
    ) -> list[dict]:
        sql = """SELECT c.id AS copy_id,c.copy_uuid,c.copy_code,c.copy_number,c.format,c.condition,c.location,c.photo_path,c.price_minor,
                        c.price_minor AS display_price_minor,c.status,
                        b.id AS book_id,b.title,b.author,b.isbn,b.genre,b.publisher,b.publication_year,b.edition,b.page_count,b.book_details,b.srp_minor,
                        s.sale_date,b.metadata_source,b.metadata_status
                 FROM copies c JOIN book_records b ON b.id=c.book_id
                 LEFT JOIN sales s ON s.id=(SELECT MAX(s2.id) FROM sales s2 WHERE s2.copy_id=c.id)
                 WHERE NOT EXISTS (SELECT 1 FROM trash_entries t WHERE t.copy_id=c.id)
                   AND NOT EXISTS (SELECT 1 FROM storage_operations o WHERE o.copy_id=c.id)"""
        args: list = []
        if search.strip():
            q = f"%{search.strip()}%"
            sql += " AND (b.title LIKE ? OR b.author LIKE ? OR b.isbn LIKE ? OR c.copy_code LIKE ? OR c.format LIKE ? OR c.location LIKE ?)"
            args.extend([q, q, q, q, q, q])
        if status != "All":
            sql += " AND c.status=?"
            args.append(status)
        if genre != "All":
            sql += " AND b.genre=?"
            args.append(genre)
        if condition != "All":
            sql += " AND c.condition=?"
            args.append(condition)
        if location != "All":
            sql += " AND c.location=?"
            args.append(location)
        sql += " ORDER BY (c.status='Sold'), b.title COLLATE NOCASE, c.copy_number"
        with self.db.connect() as conn:
            return [dict(row) for row in conn.execute(sql, args).fetchall()]

    def list_sales(self) -> list[dict]:
        sql = """SELECT s.id AS sale_id,s.copy_id,c.copy_code,b.title,b.author,
                        s.sale_date,s.price_minor,s.voided_at,s.void_reason
                 FROM sales s JOIN copies c ON c.id=s.copy_id
                 JOIN book_records b ON b.id=c.book_id
                 WHERE NOT EXISTS (SELECT 1 FROM trash_entries t WHERE t.copy_id=c.id)
                   AND NOT EXISTS (SELECT 1 FROM storage_operations o WHERE o.copy_id=c.id)
                 ORDER BY s.sale_date DESC,s.id DESC"""
        with self.db.connect() as conn:
            return [dict(row) for row in conn.execute(sql).fetchall()]

    def get_copy(self, copy_id: int) -> dict | None:
        rows = self.list_copies()
        return next((r for r in rows if r["copy_id"] == copy_id), None)

    def get_copy_details(self, copy_id: int) -> dict | None:
        """Return a copy with its complete sale/reversal history."""
        with self.db.connect() as conn:
            row = conn.execute(
                """SELECT c.id AS copy_id,c.copy_uuid,c.copy_code,c.copy_number,c.format,c.condition,c.location,c.photo_path,
                          c.price_minor,c.price_minor AS display_price_minor,c.status,
                          b.id AS book_id,b.title,b.author,b.isbn,b.genre,b.publisher,b.publication_year,b.edition,
                          b.page_count,b.book_details,b.srp_minor,b.metadata_source,b.metadata_status,
                          (SELECT s.sale_date FROM sales s WHERE s.copy_id=c.id ORDER BY s.id DESC LIMIT 1) AS sale_date
                   FROM copies c JOIN book_records b ON b.id=c.book_id WHERE c.id=?""",
                (copy_id,),
            ).fetchone()
            if row is None:
                return None
            copy = dict(row)
            rows = conn.execute(
                """SELECT id AS sale_id,sale_date,price_minor,voided_at,void_reason
                   FROM sales WHERE copy_id=? ORDER BY sale_date,id""",
                (copy_id,),
            ).fetchall()
        copy["sale_history"] = [dict(row) for row in rows]
        return copy

    def update_copy(self, copy_id: int, payload: dict, *, isbn_override: bool = False) -> None:
        errors = self.validate(payload, isbn_override=isbn_override)
        if errors:
            raise ValidationError(errors)
        price_minor = int(round(float(str(payload["price"]).replace(",", "")) * 100))
        srp_value = payload.get("srp")
        srp_minor = int(round(float(srp_value) * 100)) if srp_value not in (None, "") else None
        isbn = normalize_isbn(payload.get("isbn"))
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            errors = self.validate(payload, isbn_override=isbn_override, conn=conn)
            if errors:
                raise ValidationError(errors)
            row = conn.execute("SELECT book_id,status,price_minor,photo_path FROM copies c WHERE id=? AND NOT EXISTS (SELECT 1 FROM trash_entries t WHERE t.copy_id=c.id) AND NOT EXISTS (SELECT 1 FROM storage_operations o WHERE o.copy_id=c.id)", (copy_id,)).fetchone()
            if not row:
                raise KeyError(f"Copy {copy_id} was not found")
            if row["status"] == "Sold" and price_minor != row["price_minor"]:
                raise ValidationError({"price": "Price is locked while this copy is Sold. Change its status before editing Price."})
            book_id = row["book_id"]
            try:
                conn.execute(
                    """UPDATE book_records SET title=?,author=?,isbn=?,genre=?,book_details=?,publisher=?,publication_year=?,edition=?,page_count=?,srp_minor=?,metadata_source=?,metadata_status=?,updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?""",
                    (payload["title"].strip(),payload["author"].strip(),isbn,payload["genre"],(payload.get("book_details") or "").strip() or None,
                     (payload.get("publisher") or "").strip() or None,int(payload["publication_year"]) if str(payload.get("publication_year") or "").isdigit() else None,
                     (payload.get("edition") or "").strip() or None,int(payload["page_count"]) if str(payload.get("page_count") or "").isdigit() else None,
                     srp_minor,payload.get("metadata_source"),payload.get("metadata_status","Manual entry"),book_id),
                )
            except sqlite3.IntegrityError as exc:
                raise ValidationError({"isbn": "Another bibliographic record already uses this ISBN."}) from exc
            conn.execute(
                """UPDATE copies SET format=?,condition=?,location=?,photo_path=?,price_minor=?,updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?""",
                (payload["format"].strip(),payload["condition"].strip(),self._canonical_location(conn,payload.get("location")),
                 row["photo_path"],price_minor,copy_id),
            )
            new_photo = self._resolve_photo(payload["photo_path"])
            try:
                new_photo.resolve().relative_to(self.photos.staging_dir.resolve())
                is_staged = True
            except ValueError:
                is_staged = False
            if is_staged:
                conn.execute("INSERT INTO storage_operations(operation,copy_id,source_path,target_path,state) VALUES('replace',?,?,?,'prepared')",
                             (copy_id, new_photo.resolve().relative_to(self.data_dir.resolve()).as_posix(), row["photo_path"]))
            conn.commit()
        if is_staged:
            try:
                self.photos.replace(copy_id, new_photo)
                with self.db.connect() as conn:
                    conn.execute("DELETE FROM storage_operations WHERE operation='replace' AND copy_id=?", (copy_id,))
            except Exception as exc:
                raise ValidationError({"photo_path": f"Photo replacement needs recovery: {exc}"}) from exc

    def change_status(self, copy_id: int, status: str, *, void_reason: str | None = None) -> None:
        if status not in COPY_STATUSES:
            raise ValidationError({"status": "Choose a valid status."})
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            current = conn.execute("SELECT status,price_minor FROM copies c WHERE id=? AND NOT EXISTS (SELECT 1 FROM trash_entries t WHERE t.copy_id=c.id) AND NOT EXISTS (SELECT 1 FROM storage_operations o WHERE o.copy_id=c.id)", (copy_id,)).fetchone()
            if not current:
                raise KeyError(f"Copy {copy_id} was not found")
            if current["status"] == status:
                raise ValidationError({"status": "This copy already has that status."})
            if current["status"] == "Sold" and void_reason not in SALE_VOID_REASONS:
                raise ValidationError({"void_reason": "Choose a valid reason for voiding the sale."})
            if status == "Sold" and (current["price_minor"] is None or current["price_minor"] <= 0):
                raise ValidationError({"price": "Enter a valid current Price greater than PHP 0 before marking Sold."})
            active_sale = conn.execute(
                "SELECT id FROM sales WHERE copy_id=? AND voided_at IS NULL ORDER BY id DESC LIMIT 1",
                (copy_id,),
            ).fetchone()
            if status == "Sold" and active_sale:
                raise ValidationError({"status": "This copy already has an active sale record."})
            if current["status"] == "Sold":
                if not active_sale:
                    raise ValidationError({"status": "This Sold copy has no active sale record; its status was not changed."})
                voided = conn.execute(
                    "UPDATE sales SET voided_at=strftime('%Y-%m-%dT%H:%M:%fZ','now'),void_reason=? WHERE id=? AND voided_at IS NULL",
                    (void_reason, active_sale["id"]),
                )
                if voided.rowcount != 1:
                    raise ValidationError({"status": "The active sale changed before it could be reversed; refresh and try again."})
            conn.execute("UPDATE copies SET status=?,updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?", (status, copy_id))
            if status == "Sold":
                try:
                    conn.execute("INSERT INTO sales(copy_id,price_minor,sale_date) VALUES(?,?,?)", (copy_id, current["price_minor"], date.today().isoformat()))
                except sqlite3.IntegrityError as exc:
                    raise ValidationError({"status": "This copy already has an active sale record."}) from exc
            conn.commit()

    @staticmethod
    def status_change_requires_confirmation(current_status: str, target_status: str) -> bool:
        return current_status != target_status and current_status in {"Not for Sale", "Sold"}

    def counts(self) -> dict[str, int]:
        with self.db.connect() as conn:
            result = {status: 0 for status in COPY_STATUSES}
            for row in conn.execute("SELECT status, COUNT(*) AS n FROM copies c WHERE NOT EXISTS (SELECT 1 FROM trash_entries t WHERE t.copy_id=c.id) AND NOT EXISTS (SELECT 1 FROM storage_operations o WHERE o.copy_id=c.id) GROUP BY status"):
                result[row["status"]] = row["n"]
            result["Total copies"] = sum(result.values())
            distinct_titles = conn.execute("SELECT COUNT(DISTINCT c.book_id) FROM copies c WHERE NOT EXISTS (SELECT 1 FROM trash_entries t WHERE t.copy_id=c.id) AND NOT EXISTS (SELECT 1 FROM storage_operations o WHERE o.copy_id=c.id)").fetchone()[0]
            result["Distinct Titles"] = distinct_titles
            # Retain the existing service key for callers that still use the older label.
            result["Bibliographic records"] = distinct_titles
            return result
