from __future__ import annotations
from datetime import date
from pathlib import Path
import sqlite3
from bookledger.config import APPROVED_GENRES, COPY_STATUSES, DEFAULT_LOCATION
from bookledger.db.database import Database
from bookledger.services.isbn import isbn_check, normalize_isbn

REQUIRED_COPY_FIELDS = ("title", "author", "genre", "format", "condition", "price", "photo_path")


class ValidationError(ValueError):
    def __init__(self, errors: dict[str, str]):
        self.errors = errors
        super().__init__("The form contains invalid or missing fields.")


class CatalogService:
    def __init__(self, db: Database, data_dir: str | Path | None = None):
        self.db = db
        self.data_dir = Path(data_dir) if data_dir else db.path.parent

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

    def validate(self, payload: dict, *, isbn_override: bool = False) -> dict[str, str]:
        errors: dict[str, str] = {}
        for field in ("title", "author", "genre", "format", "condition", "photo_path"):
            if not str(payload.get(field) or "").strip():
                errors[field] = "Required."
        genre = str(payload.get("genre") or "").strip()
        if genre and genre not in APPROVED_GENRES:
            errors["genre"] = "Choose one of the approved genres."
        try:
            price = float(str(payload.get("price") or "").replace(",", ""))
            if price <= 0:
                errors["price"] = "Price must be greater than PHP 0."
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

    def create_copy(self, payload: dict, *, isbn_override: bool = False, existing_book_id: int | None = None) -> int:
        errors = self.validate(payload, isbn_override=isbn_override)
        if errors:
            raise ValidationError(errors)
        price_minor = int(round(float(str(payload["price"]).replace(",", "")) * 100))
        srp_value = payload.get("srp")
        srp_minor = int(round(float(srp_value) * 100)) if srp_value not in (None, "") else None
        isbn = normalize_isbn(payload.get("isbn"))
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
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
            location = (payload.get("location") or "").strip() or DEFAULT_LOCATION
            cur = conn.execute(
                """INSERT INTO copies(book_id,copy_number,format,condition,location,photo_path,price_minor,status)
                   VALUES(?,?,?,?,?,?,?,?)""",
                (book_id, next_number, payload["format"].strip(), payload["condition"].strip(), location,
                 self._stored_photo_path(payload["photo_path"]), price_minor, "Available"),
            )
            copy_id = int(cur.lastrowid)
            code = f"BL-{copy_id:06d}"
            conn.execute("UPDATE copies SET copy_code=? WHERE id=?", (code, copy_id))
            conn.commit()
            return copy_id

    def list_copies(self, search: str = "", status: str = "All", genre: str = "All") -> list[dict]:
        sql = """SELECT c.id AS copy_id,c.copy_code,c.copy_number,c.format,c.condition,c.location,c.photo_path,c.price_minor,c.status,
                        b.id AS book_id,b.title,b.author,b.isbn,b.genre,b.publisher,b.publication_year,b.edition,b.page_count,b.book_details,b.srp_minor,
                        s.actual_sale_price_minor,s.sale_date,b.metadata_source,b.metadata_status
                 FROM copies c JOIN book_records b ON b.id=c.book_id LEFT JOIN sales s ON s.copy_id=c.id WHERE 1=1"""
        args: list = []
        if search.strip():
            q = f"%{search.strip()}%"
            sql += " AND (b.title LIKE ? OR b.author LIKE ? OR b.isbn LIKE ? OR c.copy_code LIKE ?)"
            args.extend([q, q, q, q])
        if status != "All":
            sql += " AND c.status=?"
            args.append(status)
        if genre != "All":
            sql += " AND b.genre=?"
            args.append(genre)
        sql += " ORDER BY b.title COLLATE NOCASE, c.copy_number"
        with self.db.connect() as conn:
            return [dict(row) for row in conn.execute(sql, args).fetchall()]

    def get_copy(self, copy_id: int) -> dict | None:
        rows = self.list_copies()
        return next((r for r in rows if r["copy_id"] == copy_id), None)

    def update_copy(self, copy_id: int, payload: dict, *, isbn_override: bool = False) -> None:
        errors = self.validate(payload, isbn_override=isbn_override)
        if errors:
            raise ValidationError(errors)
        price_minor = int(round(float(str(payload["price"]).replace(",", "")) * 100))
        srp_value = payload.get("srp")
        srp_minor = int(round(float(srp_value) * 100)) if srp_value not in (None, "") else None
        isbn = normalize_isbn(payload.get("isbn"))
        status = payload.get("status", "Available")
        if status not in COPY_STATUSES:
            raise ValidationError({"status": "Choose a valid status."})
        actual_price = payload.get("actual_sale_price")
        sale_date = (payload.get("sale_date") or "").strip()
        if status == "Sold":
            try:
                actual_minor = int(round(float(str(actual_price).replace(",", "")) * 100))
                if actual_minor <= 0:
                    raise ValueError
            except (TypeError, ValueError):
                raise ValidationError({"actual_sale_price": "Enter the actual sale price, greater than PHP 0."})
            try:
                date.fromisoformat(sale_date)
            except ValueError:
                raise ValidationError({"sale_date": "Enter the sale date in YYYY-MM-DD format."})
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT book_id FROM copies WHERE id=?", (copy_id,)).fetchone()
            if not row:
                raise KeyError(f"Copy {copy_id} was not found")
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
                """UPDATE copies SET format=?,condition=?,location=?,photo_path=?,price_minor=?,status=?,updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?""",
                (payload["format"].strip(),payload["condition"].strip(),(payload.get("location") or "").strip() or DEFAULT_LOCATION,
                 self._stored_photo_path(payload["photo_path"]),price_minor,status,copy_id),
            )
            if status == "Sold":
                conn.execute(
                    """INSERT INTO sales(copy_id,actual_sale_price_minor,sale_date) VALUES(?,?,?)
                       ON CONFLICT(copy_id) DO UPDATE SET actual_sale_price_minor=excluded.actual_sale_price_minor,sale_date=excluded.sale_date""",
                    (copy_id,actual_minor,sale_date),
                )
            # Historical sale rows are deliberately retained if status changes away from Sold.
            conn.commit()

    def counts(self) -> dict[str, int]:
        with self.db.connect() as conn:
            result = {status: 0 for status in COPY_STATUSES}
            for row in conn.execute("SELECT status, COUNT(*) AS n FROM copies GROUP BY status"):
                result[row["status"]] = row["n"]
            result["Total copies"] = sum(result.values())
            result["Bibliographic records"] = conn.execute("SELECT COUNT(*) FROM book_records").fetchone()[0]
            return result
