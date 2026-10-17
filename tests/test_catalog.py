from pathlib import Path
import sqlite3

import pytest
from PIL import Image

from bookledger.config import APPROVED_GENRES, COPY_STATUSES, DEFAULT_LOCATION
from bookledger.db.database import Database
from bookledger.services.backups import BackupService
from bookledger.services.catalog import CatalogService, ValidationError
from bookledger.services.isbn import isbn_check, normalize_isbn
from bookledger.services.photos import PhotoService


@pytest.fixture
def setup(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    db = Database(data / "bookledger.sqlite3")
    photo_service = PhotoService(data / "photos")
    source = tmp_path / "sample.png"
    Image.new("RGB", (2200, 1400), "white").save(source)
    photo = photo_service.import_and_compress(source)
    service = CatalogService(db)
    payload = {
        "title": "Test Book", "author": "Test Author", "isbn": "9780306406157",
        "genre": "Science", "format": "Paperback", "condition": "Good",
        "location": "", "price": "500", "photo_path": str(photo), "srp": "600",
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


def test_copy_filters_and_dashboard_counts_use_physical_and_record_levels(setup):
    _, _, _, service, payload, _ = setup
    first = service.create_copy({**payload, "location": "Shelf A", "condition": "Good"})
    shared_book = service.duplicate_by_isbn(payload["isbn"])
    service.create_copy({**payload, "location": "Shelf B", "condition": "Like New"}, existing_book_id=shared_book["id"])
    service.create_copy({**payload, "title": "Second Record", "isbn": "9780140449136", "genre": "History", "location": "Shelf A", "condition": "Good"})

    filtered = service.list_copies(genre="Science", condition="Good", location="Shelf A", status="Available")
    assert [row["copy_id"] for row in filtered] == [first]
    assert service.list_copies(location="Shelf B")[0]["condition"] == "Like New"
    service.update_copy(first, {**payload, "location": "Shelf A", "condition": "Good", "status": "Sold", "actual_sale_price": "425", "sale_date": "2026-10-17"})

    counts = service.counts()
    assert counts["Total copies"] == 3
    assert counts["Distinct Titles"] == 2
    assert counts["Bibliographic records"] == 2
    assert counts["Sold"] == 1


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


def test_different_isbn_does_not_match_as_duplicate(setup):
    _, _, _, service, payload, _ = setup
    service.create_copy(payload)
    assert service.duplicate_by_isbn("9780140449136") is None


def test_no_isbn_title_author_duplicate_search(setup):
    _, _, _, service, payload, _ = setup
    no_isbn = {**payload, "isbn": None}
    service.create_copy(no_isbn)
    assert len(service.no_isbn_title_author_matches("test book", "TEST AUTHOR")) == 1


def test_sale_record_persists_when_status_changes_away_from_sold(setup):
    _, _, _, service, payload, _ = setup
    copy_id = service.create_copy(payload)
    edit = {**payload, "status": "Sold", "actual_sale_price": "480", "sale_date": "2026-10-17"}
    service.update_copy(copy_id, edit)
    row = service.get_copy(copy_id)
    assert row["status"] == "Sold"
    assert row["actual_sale_price_minor"] == 48000
    assert row["sale_date"] == "2026-10-17"
    edit["status"] = "Listed"
    service.update_copy(copy_id, edit)
    row = service.get_copy(copy_id)
    assert row["status"] == "Listed"
    assert row["actual_sale_price_minor"] == 48000  # retained as historical information


def test_invalid_sold_record_is_rejected(setup):
    _, _, _, service, payload, _ = setup
    copy_id = service.create_copy(payload)
    with pytest.raises(ValidationError) as exc:
        service.update_copy(copy_id, {**payload, "status": "Sold", "actual_sale_price": "", "sale_date": ""})
    assert "actual_sale_price" in exc.value.errors


def test_non_finite_actual_sale_price_is_rejected(setup):
    _, _, _, service, payload, _ = setup
    copy_id = service.create_copy(payload)
    with pytest.raises(ValidationError) as exc:
        service.update_copy(copy_id, {**payload, "status": "Sold", "actual_sale_price": "inf", "sale_date": "2026-10-17"})
    assert "actual_sale_price" in exc.value.errors


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
    other_photo_dir.mkdir(parents=True)
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
        edit = {**payload, "status": status}
        if status == "Sold":
            edit.update(actual_sale_price="450", sale_date="2026-10-17")
        service.update_copy(copy_id, edit)
        assert service.get_copy(copy_id)["status"] == status
