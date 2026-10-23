from pathlib import Path
import sqlite3
import uuid
from datetime import date as real_date

import pytest
from PIL import Image

from bookledger.config import APPROVED_GENRES, COPY_STATUSES, DEFAULT_FORMATS, DEFAULT_LOCATION
from bookledger.db.database import Database, SCHEMA
from bookledger.services.backups import BackupService
from bookledger.services.catalog import CatalogService, ValidationError
from bookledger.services import catalog as catalog_module
from bookledger.services.isbn import isbn_check, normalize_isbn
from bookledger.services.photos import PhotoService
from bookledger.services.reports import ReportService


@pytest.fixture
def setup(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    db = Database(data / "bookledger.sqlite3")
    photo_service = PhotoService(data / "photos")
    source = tmp_path / "sample.png"
    Image.new("RGB", (2200, 1400), "white").save(source)
    photo = photo_service.import_and_compress(source)
    reusable_source = data / "selected-photo.png"
    Image.new("RGB", (2200, 1400), "white").save(reusable_source)
    service = CatalogService(db)
    payload = {
        "title": "Test Book", "author": "Test Author", "isbn": "9780306406157",
        "genre": "Science", "format": "Paperback", "condition": "Good",
        "location": "", "price": "500", "photo_path": str(reusable_source), "srp": "600",
        "book_details": "A test synopsis", "publisher": "Test Press", "publication_year": "2020",
        "edition": "1st", "page_count": "120", "metadata_source": "Test", "metadata_status": "Retrieved",
    }
    return tmp_path, data, db, service, payload, photo


def test_isbn_check_digits_and_normalization():
    assert normalize_isbn("978-0-306-40615-7") == "9780306406157"
    assert isbn_check("9780306406157")[0]
    assert not isbn_check("9780306406158")[0]
    assert isbn_check("0-306-40615-2")[0]
    assert isbn_check(None)[0]


def test_required_fields_price_and_genre_are_validated(setup):
    _, _, _, service, payload, _ = setup
    invalid = {**payload, "price": "0", "genre": "Astronomy"}
    errors = service.validate(invalid)
    assert "price" in errors
    assert "genre" in errors
    invalid = {**payload, "photo_path": "", "title": ""}
    errors = service.validate(invalid)
    assert "photo_path" in errors and "title" in errors
    for invalid_price in ("nan", "inf", "-inf", "1e308"):
        assert "price" in service.validate({**payload, "price": invalid_price})


def test_catalog_service_rejects_unapproved_genres(setup):
    _, _, _, service, payload, _ = setup
    with pytest.raises(ValidationError) as exc:
        service.create_copy({**payload, "genre": "Astronomy"})
    assert "genre" in exc.value.errors


def test_create_copy_assigns_copy_id_and_default_location(setup):
    _, _, _, service, payload, _ = setup
    copy_id = service.create_copy(payload)
    row = service.get_copy(copy_id)
    assert row["copy_code"] == f"BL-{copy_id:06d}"
    assert row["status"] == "Available"
    assert row["location"] == DEFAULT_LOCATION
    assert row["price_minor"] == 50000
    assert row["srp_minor"] == 60000
    assert row["display_price_minor"] == 50000


def test_missing_optional_metadata_is_stored_as_null(setup):
    _, _, db, service, payload, _ = setup
    copy_id = service.create_copy({**payload, "book_details": "", "publisher": "", "publication_year": "", "edition": "", "page_count": "", "srp": ""})
    with db.connect() as conn:
        row = conn.execute("SELECT book_details,publisher,publication_year,edition,page_count,srp_minor FROM book_records").fetchone()
    assert tuple(row) == (None, None, None, None, None, None)


def test_copy_filters_and_dashboard_counts_use_physical_and_record_levels(setup):
    _, _, _, service, payload, _ = setup
    service.add_location("Shelf A")
    service.add_location("Shelf B")
    first = service.create_copy({**payload, "location": "Shelf A", "condition": "Good"})
    shared_book = service.duplicate_by_isbn(payload["isbn"])
    service.create_copy({**payload, "location": "Shelf B", "condition": "Like New"}, existing_book_id=shared_book["id"])
    service.create_copy({**payload, "title": "Second Record", "isbn": "9780140449136", "genre": "History", "location": "Shelf A", "condition": "Good"})

    filtered = service.list_copies(genre="Science", condition="Good", location="Shelf A", status="Available")
    assert [row["copy_id"] for row in filtered] == [first]
    assert service.list_copies(location="Shelf B")[0]["condition"] == "Like New"
    service.change_status(first, "Sold")

    counts = service.counts()
    assert counts["Total copies"] == 3
    assert counts["Distinct Titles"] == 2
    assert counts["Bibliographic records"] == 2
    assert counts["Sold"] == 1


def test_filtered_copy_queries_always_return_sold_items_last(setup):
    _, _, _, service, payload, _ = setup
    sold_id = service.create_copy({**payload, "title": "A Book"})
    available_id = service.create_copy({**payload, "title": "Z Book", "isbn": "9780140449136"})
    service.change_status(sold_id, "Sold")
    rows = service.list_copies(search="Book", genre="Science", condition="Good", location=DEFAULT_LOCATION)
    assert [row["copy_id"] for row in rows] == [available_id, sold_id]


def test_exact_isbn_duplicate_requires_reusing_record(setup):
    _, _, _, service, payload, _ = setup
    first = service.create_copy(payload)
    existing = service.duplicate_by_isbn(payload["isbn"])
    second_payload = {**payload, "photo_path": payload["photo_path"], "price": "450", "condition": "Acceptable"}
    second = service.create_copy(second_payload, existing_book_id=existing["id"])
    assert first != second
    assert len(service.list_copies()) == 2
    assert len({r["book_id"] for r in service.list_copies()}) == 1
    assert [r["copy_number"] for r in service.list_copies()] == [1, 2]


def test_copy_numbers_start_independently_for_separate_bibliographic_records(setup):
    _, _, _, service, payload, _ = setup
    first = service.create_copy(payload)
    separate = service.create_copy({**payload, "isbn": "9780140449136", "title": "Separate Book"})

    assert service.get_copy(first)["copy_number"] == 1
    assert service.get_copy(separate)["copy_number"] == 1


def test_different_isbn_does_not_match_as_duplicate(setup):
    _, _, _, service, payload, _ = setup
    service.create_copy(payload)
    assert service.duplicate_by_isbn("9780140449136") is None


def test_no_isbn_title_author_duplicate_search(setup):
    _, _, _, service, payload, _ = setup
    no_isbn = {**payload, "isbn": None}
    service.create_copy(no_isbn)
    assert len(service.no_isbn_title_author_matches("test book", "TEST AUTHOR")) == 1


@pytest.mark.parametrize("destination", ("Available", "Listed", "Not for Sale"))
def test_sale_reversal_voids_original_and_preserves_history(setup, monkeypatch, destination):
    _, _, _, service, payload, _ = setup
    class FrozenDate:
        @classmethod
        def today(cls):
            return real_date(2026, 10, 18)
    monkeypatch.setattr(catalog_module, "date", FrozenDate)
    copy_id = service.create_copy(payload)
    service.change_status(copy_id, "Sold")
    row = service.get_copy(copy_id)
    assert row["status"] == "Sold"
    assert row["sale_date"] == "2026-10-18"
    assert service.list_sales()[0]["price_minor"] == 50000
    service.change_status(copy_id, destination, void_reason="Cancelled Order")
    row = service.get_copy(copy_id)
    sale = service.list_sales()[0]
    assert row["status"] == destination
    assert sale["price_minor"] == 50000
    assert sale["sale_date"] == "2026-10-18"
    assert sale["voided_at"]
    assert sale["void_reason"] == "Cancelled Order"
    assert ReportService(service.db).sales_revenue() == 0


@pytest.mark.parametrize("reason", ("Marked Sold by Mistake", "Cancelled Order", "Returned Order", "Test"))
def test_all_predefined_void_reasons_are_persisted(setup, reason):
    _, _, _, service, payload, _ = setup
    copy_id = service.create_copy(payload)
    service.change_status(copy_id, "Sold")
    service.change_status(copy_id, "Available", void_reason=reason)
    sale = service.list_sales()[0]
    assert sale["void_reason"] == reason
    assert sale["voided_at"]


@pytest.mark.parametrize("reason", (None, "free text", ""))
def test_missing_or_invalid_void_reason_cannot_change_sale_or_copy(setup, reason):
    _, _, _, service, payload, _ = setup
    copy_id = service.create_copy(payload)
    service.change_status(copy_id, "Sold")
    with pytest.raises(ValidationError) as exc:
        service.change_status(copy_id, "Available", void_reason=reason)
    assert "valid reason" in exc.value.errors["void_reason"]
    assert service.get_copy(copy_id)["status"] == "Sold"
    assert service.list_sales()[0]["voided_at"] is None


def test_contextual_price_edits_sale_price_without_overwriting_asking_price(setup):
    _, _, _, service, payload, _ = setup
    copy_id = service.create_copy(payload)
    service.change_status(copy_id, "Sold")
    with pytest.raises(ValidationError) as exc:
        service.update_copy(copy_id, {**payload, "price": "510"})
    assert "price" in exc.value.errors
    row = service.get_copy(copy_id)
    assert row["price_minor"] == 50000
    assert row["display_price_minor"] == 50000
    assert service.list_sales()[0]["price_minor"] == 50000
    service.change_status(copy_id, "Available", void_reason="Returned Order")
    service.update_copy(copy_id, {**payload, "price": "525"})
    row = service.get_copy(copy_id)
    assert row["price_minor"] == row["display_price_minor"] == 52500
    assert service.list_sales()[0]["price_minor"] == 50000
    assert service.list_sales()[0]["voided_at"]


def test_edit_payload_cannot_change_copy_status_implicitly(setup):
    _, _, _, service, payload, _ = setup
    copy_id = service.create_copy(payload)
    service.change_status(copy_id, "Listed")
    service.update_copy(copy_id, {**payload, "status": "Sold", "actual_sale_price": "999", "sale_date": "2026-10-17"})
    assert service.get_copy(copy_id)["status"] == "Listed"
    assert service.list_sales() == []


def test_reversed_copy_can_be_sold_again_with_new_price_date_and_active_revenue(setup, monkeypatch):
    _, _, _, service, payload, _ = setup
    dates = iter((real_date(2026, 10, 18), real_date(2026, 11, 2)))

    class FrozenDate:
        @classmethod
        def today(cls):
            return next(dates)

    monkeypatch.setattr(catalog_module, "date", FrozenDate)
    copy_id = service.create_copy(payload)
    service.change_status(copy_id, "Sold")
    service.change_status(copy_id, "Available", void_reason="Cancelled Order")
    service.update_copy(copy_id, {**payload, "price": "725"})
    service.change_status(copy_id, "Sold")

    rows = service.list_sales()
    assert len(rows) == 2
    new_sale, original = rows
    assert original["voided_at"]
    assert (original["sale_date"], original["price_minor"]) == ("2026-10-18", 50000)
    assert new_sale["voided_at"] is None
    assert (new_sale["sale_date"], new_sale["price_minor"]) == ("2026-11-02", 72500)
    assert ReportService(service.db).sales_revenue() == 72500
    assert service.get_copy(copy_id)["status"] == "Sold"


def test_copy_details_returns_every_sale_and_void_in_chronological_order(setup):
    _, _, _, service, payload, _ = setup
    copy_id = service.create_copy(payload)
    service.change_status(copy_id, "Sold")
    service.change_status(copy_id, "Available", void_reason="Returned Order")
    service.update_copy(copy_id, {**payload, "price": "725"})
    service.change_status(copy_id, "Sold")
    details = service.get_copy_details(copy_id)
    history = details["sale_history"]
    assert len(history) == 2
    assert history[0]["void_reason"] == "Returned Order"
    assert history[0]["voided_at"]
    assert history[0]["price_minor"] == 50000
    assert history[1]["voided_at"] is None
    assert history[1]["void_reason"] is None
    assert history[1]["price_minor"] == 72500


def test_active_sale_unique_index_prevents_second_active_event(setup):
    _, _, db, service, payload, _ = setup
    copy_id = service.create_copy(payload)
    service.change_status(copy_id, "Sold")

    with pytest.raises(sqlite3.IntegrityError):
        with db.connect() as conn:
            conn.execute("INSERT INTO sales(copy_id,price_minor,sale_date) VALUES(?,?,?)", (copy_id, 40000, "2026-10-19"))


def test_failed_status_update_rolls_back_sale_reversal(setup):
    _, _, db, service, payload, _ = setup
    copy_id = service.create_copy(payload)
    service.change_status(copy_id, "Sold")
    with db.connect() as conn:
        conn.execute(
            """CREATE TRIGGER fail_status_update BEFORE UPDATE OF status ON copies
               WHEN NEW.status='Available' BEGIN SELECT RAISE(ABORT,'forced failure'); END"""
        )

    with pytest.raises(sqlite3.IntegrityError, match="forced failure"):
        service.change_status(copy_id, "Available", void_reason="Test")

    assert service.get_copy(copy_id)["status"] == "Sold"
    assert service.list_sales()[0]["voided_at"] is None


def test_non_finite_price_is_rejected_before_sold_status_can_be_set(setup):
    _, _, _, service, payload, _ = setup
    copy_id = service.create_copy(payload)
    with pytest.raises(ValidationError) as exc:
        service.update_copy(copy_id, {**payload, "price": "inf"})
    assert "price" in exc.value.errors


def test_database_connections_close_after_success_and_exception(setup):
    _, _, db, _, _, _ = setup

    with db.connect() as conn:
        conn.execute("SELECT 1")
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        conn.execute("SELECT 1")

    with pytest.raises(RuntimeError, match="expected failure"):
        with db.connect() as failed_conn:
            raise RuntimeError("expected failure")
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        failed_conn.execute("SELECT 1")


def test_photo_compression_and_backup_integrity(setup):
    _, data, db, service, payload, photo = setup
    assert Image.open(photo).width <= 1600
    service.create_copy(payload)
    backups = BackupService(db, data, data / "backups")
    archive = backups.create_backup()
    ok, message = backups.verify_archive(archive)
    assert ok, message


def test_restore_replaces_database_and_photos_safely(setup, tmp_path):
    _, data, db, service, payload, photo = setup
    service.create_copy(payload)
    backups = BackupService(db, data, data / "backups")
    archive = backups.create_backup()

    other_data = tmp_path / "other-data"
    other_db = Database(other_data / "bookledger.sqlite3")
    other_service = CatalogService(other_db)
    other_photo_dir = other_data / "photos"
    other_photo_dir.mkdir(parents=True, exist_ok=True)
    other_image = tmp_path / "other.png"
    Image.new("RGB", (80, 80), "black").save(other_image)
    other_photo = PhotoService(other_photo_dir).import_and_compress(other_image)
    other_payload = {**payload, "title": "Other book", "author": "Other author", "isbn": None, "photo_path": str(other_photo)}
    other_service.create_copy(other_payload)
    other_backups = BackupService(other_db, other_data, other_data / "backups")
    other_backups.restore_backup(archive)
    restored = CatalogService(Database(other_data / "bookledger.sqlite3")).list_copies()
    assert len(restored) == 1
    assert restored[0]["title"] == "Test Book"
    assert (other_data / restored[0]["photo_path"]).is_file()


def test_invalid_isbn_can_be_overridden_explicitly(setup):
    _, _, _, service, payload, _ = setup
    invalid = {**payload, "isbn": "9780306406158"}
    assert "isbn" in service.validate(invalid)
    assert "isbn" not in service.validate(invalid, isbn_override=True)


def test_all_four_statuses_are_supported(setup):
    _, _, _, service, payload, _ = setup
    copy_id = service.create_copy(payload)
    for status in COPY_STATUSES:
        if status != "Available":
            service.change_status(copy_id, status, **({"void_reason": "Test"} if service.get_copy(copy_id)["status"] == "Sold" else {}))
        assert service.get_copy(copy_id)["status"] == status


@pytest.mark.parametrize(
    ("current", "target"),
    [(current, target) for current in COPY_STATUSES for target in COPY_STATUSES if current != target],
)
def test_every_distinct_status_transition_is_supported(setup, current, target):
    _, _, _, service, payload, _ = setup
    copy_id = service.create_copy(payload)
    if current != "Available":
        service.change_status(copy_id, current)
    service.change_status(copy_id, target, **({"void_reason": "Test"} if current == "Sold" else {}))
    assert service.get_copy(copy_id)["status"] == target


@pytest.mark.parametrize("current", ("Not for Sale", "Sold"))
@pytest.mark.parametrize("target", ("Available", "Listed", "Not for Sale", "Sold"))
def test_status_confirmation_policy_requires_confirmation_when_leaving_protected_states(current, target):
    should_confirm = current != target
    assert CatalogService.status_change_requires_confirmation(current, target) is should_confirm


@pytest.mark.parametrize("current", ("Available", "Listed"))
@pytest.mark.parametrize("target", ("Available", "Listed", "Not for Sale", "Sold"))
def test_status_confirmation_policy_does_not_prompt_for_available_or_listed(current, target):
    assert not CatalogService.status_change_requires_confirmation(current, target)


def test_location_registry_canonicalizes_and_protects_referenced_values(setup):
    _, _, _, service, payload, _ = setup
    service.add_location("Main Shelf")
    copy_id = service.create_copy({**payload, "location": "main shelf"})
    shared_book = service.duplicate_by_isbn(payload["isbn"])
    other_copy_id = service.create_copy({**payload, "location": "Main Shelf"}, existing_book_id=shared_book["id"])
    assert service.get_copy(copy_id)["location"] == "Main Shelf"
    with pytest.raises(ValidationError, match="invalid"):
        service.add_location(" main shelf ")
    with pytest.raises(ValidationError):
        service.delete_location("Main Shelf")
    service.rename_location("Main Shelf", "Front Room")
    assert service.get_copy(copy_id)["location"] == "Front Room"
    assert service.get_copy(other_copy_id)["location"] == "Front Room"
    with pytest.raises(ValidationError):
        service.delete_location("Front Room")
    service.update_copy(copy_id, {**payload, "location": DEFAULT_LOCATION})
    service.update_copy(other_copy_id, {**payload, "location": DEFAULT_LOCATION})
    service.delete_location("Front Room")
    assert "Front Room" not in service.list_locations()


def test_genre_and_format_options_seed_defaults_and_preserve_legacy_assignments(setup):
    _, _, db, service, _payload, _photo = setup
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO book_records(title,author,genre) VALUES('Legacy Genre Book','Writer','Legacy Genre')"
        )
        book_id = conn.execute("SELECT id FROM book_records WHERE title='Legacy Genre Book'").fetchone()[0]
        conn.execute(
                "INSERT INTO copies(copy_uuid,book_id,copy_number,format,condition,photo_path,price_minor) VALUES('00000000-0000-4000-8000-000000000001',?,1,'Legacy Format','Good','photos/legacy.jpg',10000)",
                (book_id,),
        )

    genres = service.list_genres()
    formats = service.list_formats()
    assert genres[:len(APPROVED_GENRES)] == APPROVED_GENRES
    assert genres[-1] == "Legacy Genre"
    assert formats[:len(DEFAULT_FORMATS)] == DEFAULT_FORMATS
    assert formats[-1] == "Legacy Format"
    assert CatalogService(db).list_genres() == genres
    assert CatalogService(db).list_formats() == formats
    with db.connect() as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 7


def test_genre_and_format_rename_migrate_assignments_atomically_and_allow_unassigned_delete(setup):
    _, _, db, service, payload, _photo = setup
    first = service.create_copy(payload)
    book_id = service.duplicate_by_isbn(payload["isbn"])["id"]
    second = service.create_copy({**payload, "location": DEFAULT_LOCATION}, existing_book_id=book_id)
    before = {row["copy_id"]: row for row in service.list_copies()}

    assert service.rename_genre("Science", "Natural Science") == "Natural Science"
    assert service.rename_format("Paperback", "Softcover") == "Softcover"
    after = {row["copy_id"]: row for row in service.list_copies()}
    assert set(after) == {first, second}
    for copy_id in (first, second):
        assert after[copy_id]["genre"] == "Natural Science"
        assert after[copy_id]["format"] == "Softcover"
        for field in ("copy_code", "title", "author", "photo_path", "price_minor", "condition", "status"):
            assert after[copy_id][field] == before[copy_id][field]
    assert service.value_assignment_count("genre", "Natural Science") == 1
    assert service.value_assignment_count("format", "Softcover") == 2
    with pytest.raises(ValidationError):
        service.delete_genre("Natural Science")
    with pytest.raises(ValidationError):
        service.delete_format("Softcover")

    service.delete_genre("History")
    service.delete_format("Other")
    assert "History" not in service.list_genres()
    assert "Other" not in service.list_formats()


def test_genre_and_format_lists_reject_blank_duplicate_and_unsupported_values(setup):
    _, _, _, service, payload, _photo = setup
    with pytest.raises(ValidationError):
        service.add_genre("  ")
    with pytest.raises(ValidationError):
        service.add_genre(" science ")
    with pytest.raises(ValidationError):
        service.rename_genre("Science", "Fiction")
    with pytest.raises(ValidationError):
        service.rename_format("Paperback", "Hardcover")
    with pytest.raises(ValidationError) as exc:
        service.create_copy({**payload, "format": "Ebook"})
    assert "format" in exc.value.errors

    service.add_genre("Speculative")
    service.add_format("Ebook")
    assert service.validate({**payload, "genre": "Speculative", "format": "Ebook"}) == {}
    with pytest.raises(ValidationError):
        service.rename_format("Paperback", "  ")


def test_v1_database_migrates_existing_locations_and_data(tmp_path):
    path = tmp_path / "v1.sqlite3"
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE book_records(id INTEGER PRIMARY KEY, title TEXT NOT NULL, author TEXT NOT NULL, isbn TEXT, genre TEXT NOT NULL, book_details TEXT, publisher TEXT, publication_year INTEGER, edition TEXT, page_count INTEGER, srp_minor INTEGER, metadata_source TEXT, metadata_status TEXT NOT NULL DEFAULT 'Manual entry', created_at TEXT DEFAULT '', updated_at TEXT DEFAULT '');
        CREATE TABLE copies(id INTEGER PRIMARY KEY, copy_code TEXT UNIQUE, book_id INTEGER NOT NULL, copy_number INTEGER NOT NULL, format TEXT NOT NULL, condition TEXT NOT NULL, location TEXT NOT NULL DEFAULT 'Not Specified', photo_path TEXT NOT NULL, price_minor INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'Available', created_at TEXT DEFAULT '', updated_at TEXT DEFAULT '');
        CREATE TABLE sales(id INTEGER PRIMARY KEY, copy_id INTEGER NOT NULL, actual_sale_price_minor INTEGER NOT NULL, sale_date TEXT NOT NULL, created_at TEXT DEFAULT '');
        CREATE TABLE app_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        INSERT INTO book_records(id,title,author,genre) VALUES(1,'Kept','Author','Science');
        INSERT INTO copies(id,book_id,copy_number,format,condition,location,photo_path,price_minor) VALUES(1,1,1,'Paperback','Good','Shelf A','photos/a.jpg',12345);
        INSERT INTO sales(id,copy_id,actual_sale_price_minor,sale_date) VALUES(1,1,9900,'2026-10-01');
        PRAGMA user_version=1;
    """)
    conn.close()
    db = Database(path)
    service = CatalogService(db)
    row = service.get_copy(1)
    assert row["title"] == "Kept"
    assert uuid.UUID(row["copy_uuid"])
    assert row["location"] == "Shelf A"
    assert "Shelf A" in service.list_locations()
    assert service.list_sales()[0]["price_minor"] == 9900
    with db.connect() as migrated:
        assert migrated.execute("PRAGMA user_version").fetchone()[0] == 7
        assert tuple(migrated.execute("SELECT price_minor,sale_date FROM sales WHERE id=1").fetchone()) == (9900, "2026-10-01")
        assert migrated.execute("SELECT voided_at FROM sales WHERE id=1").fetchone()[0]
    service.change_status(1, "Sold")
    assert len(service.list_sales()) == 2
    assert service.list_sales()[1]["price_minor"] == 9900
    assert service.list_sales()[1]["voided_at"]


def test_v4_migration_reconciles_legacy_sales_without_deleting_transactions(tmp_path):
    path = tmp_path / "v4.sqlite3"
    legacy_schema = SCHEMA.replace("    voided_at TEXT,\n", "").replace(
        "    void_reason TEXT CHECK(void_reason IS NULL OR void_reason IN (\n        'Marked Sold by Mistake','Cancelled Order','Returned Order','Test'\n    )),\n", ""
    ).replace(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_sales_one_active_copy\n    ON sales(copy_id) WHERE voided_at IS NULL;\n", ""
    ).replace("    copy_uuid TEXT NOT NULL UNIQUE,\n", "").replace(
        "CREATE TRIGGER IF NOT EXISTS copies_copy_uuid_immutable\n    BEFORE UPDATE OF copy_uuid ON copies\n    WHEN OLD.copy_uuid IS NOT NULL AND NEW.copy_uuid IS NOT OLD.copy_uuid\n    BEGIN SELECT RAISE(ABORT, 'copy UUID is immutable'); END;\n", ""
    ).replace("PRAGMA user_version = 7;", "PRAGMA user_version = 4;")
    conn = sqlite3.connect(path)
    conn.executescript(legacy_schema)
    conn.execute("INSERT INTO book_records(id,title,author,genre) VALUES(1,'Sold','Author','Science')")
    conn.execute("INSERT INTO book_records(id,title,author,genre) VALUES(2,'Available','Author','History')")
    conn.execute("INSERT INTO copies(id,copy_code,book_id,copy_number,format,condition,photo_path,price_minor,status) VALUES(1,'BL-000001',1,1,'Paperback','Good','photos/1.jpg',20000,'Sold')")
    conn.execute("INSERT INTO copies(id,copy_code,book_id,copy_number,format,condition,photo_path,price_minor,status) VALUES(2,'BL-000002',2,1,'Paperback','Good','photos/2.jpg',30000,'Available')")
    conn.execute("INSERT INTO sales(id,copy_id,price_minor,sale_date) VALUES(10,1,15000,'2026-01-01')")
    conn.execute("INSERT INTO sales(id,copy_id,price_minor,sale_date) VALUES(11,1,20000,'2026-02-02')")
    conn.execute("INSERT INTO sales(id,copy_id,price_minor,sale_date) VALUES(12,2,25000,'2026-03-03')")
    conn.commit()
    conn.close()

    db = Database(path)
    with db.connect() as migrated:
        rows = migrated.execute("SELECT id,copy_id,price_minor,sale_date,voided_at FROM sales ORDER BY id").fetchall()
        assert migrated.execute("PRAGMA user_version").fetchone()[0] == 7
        assert [(row["id"], row["price_minor"], row["sale_date"]) for row in rows] == [
            (10, 15000, "2026-01-01"), (11, 20000, "2026-02-02"), (12, 25000, "2026-03-03")
        ]
        assert rows[0]["voided_at"]
        assert rows[1]["voided_at"] is None
        assert rows[2]["voided_at"]
