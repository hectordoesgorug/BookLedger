from pathlib import Path

import pytest
from PIL import Image

from bookledger.db.database import Database
from bookledger.config_store import AppConfigStore
from bookledger.paths import AppPaths
from bookledger.services.catalog import CatalogService, ValidationError
from bookledger.services.lifecycle import CopyLifecycleService
from bookledger.services.photos import PhotoService
from bookledger.services.verification import VerificationService


def _payload(data: Path, title: str, isbn: str) -> dict:
    source = data / f"{title}.png"
    Image.new("RGB", (80, 90), "navy").save(source)
    return {
        "title": title, "author": "Test Author", "isbn": isbn, "genre": "Science",
        "format": "Paperback", "condition": "Good", "location": "",
        "price": "500", "photo_path": str(source),
    }


def test_portable_paths_are_rooted_and_do_not_depend_on_current_directory(tmp_path, monkeypatch):
    root = tmp_path / "portable"
    paths = AppPaths(root)
    other_cwd = tmp_path / "unrelated"
    other_cwd.mkdir()
    monkeypatch.chdir(other_cwd)
    paths.prepare()
    assert paths.database == root / "data" / "bookledger.sqlite3"
    assert paths.photos == root / "data" / "photos"
    assert paths.trash == root / "data" / "trash"
    assert paths.backups == root / "backups"


def test_frozen_paths_use_executable_directory_not_working_directory(tmp_path, monkeypatch):
    executable = tmp_path / "moved" / "BookLedger.exe"
    executable.parent.mkdir()
    monkeypatch.setattr("bookledger.paths.sys.frozen", True, raising=False)
    monkeypatch.setattr("bookledger.paths.sys.executable", str(executable))
    assert AppPaths().root == executable.parent.resolve()


def test_legacy_migration_copies_database_and_preserves_source_until_verified(tmp_path):
    root = tmp_path / "portable"
    legacy = root / "BookLedger_Data"
    legacy.mkdir(parents=True)
    db = Database(legacy / "bookledger.sqlite3")
    photos = PhotoService(legacy / "photos")
    image = tmp_path / "cover.png"
    Image.new("RGB", (40, 40), "green").save(image)
    staged = photos.import_and_compress(image)
    # Model a legacy relative path, preserving the primary key and copy identity.
    staged.replace(legacy / "photos" / "1.jpg")
    with db.connect() as conn:
        conn.execute("INSERT INTO book_records(id,title,author,genre) VALUES(17,'Kept','Author','Science')")
        conn.execute("INSERT INTO copies(id,copy_code,book_id,copy_number,format,condition,location,photo_path,price_minor) VALUES(23,'BL-000023',17,4,'Paperback','Good','Shelf','photos/1.jpg',50000)")
    paths = AppPaths(root)
    paths.prepare()
    assert paths.database.is_file()
    assert (legacy / "bookledger.sqlite3").is_file()
    migrated = Database(paths.database)
    paths.migrate_legacy_photos(migrated)
    with migrated.connect() as conn:
        row = conn.execute("SELECT id,copy_code,book_id,copy_number,photo_path FROM copies").fetchone()
        assert tuple(row) == (23, "BL-000023", 17, 4, "photos/23.jpg")
    assert (paths.photos / "23.jpg").is_file()
    assert (legacy / "photos" / "1.jpg").is_file()


def test_both_legacy_and_portable_databases_are_a_conflict(tmp_path):
    paths = AppPaths(tmp_path)
    paths.data.mkdir()
    paths.database.touch()
    paths.legacy_data.mkdir()
    (paths.legacy_data / "bookledger.sqlite3").touch()
    with pytest.raises(RuntimeError, match="Both portable and legacy databases exist"):
        paths.prepare()


def test_profile_configuration_migrates_to_root_and_survives_data_purge(tmp_path, monkeypatch):
    profile = tmp_path / "profile"
    legacy_config = profile / "BookLedger" / "google_books.json"
    legacy_config.parent.mkdir(parents=True)
    legacy_config.write_text('{"api_key":"portable-test"}', encoding="utf-8")
    monkeypatch.setenv("LOCALAPPDATA", str(profile))
    paths = AppPaths(tmp_path / "BookLedger")
    paths.prepare()
    db = Database(paths.database)
    config_store = AppConfigStore(paths.provider_config, paths.provider_config_fallback())
    config_store.migrate_legacy_settings(db, paths.google_books_config, paths._profile_google_books_config())
    assert config_store.get(("api_keys", "google_books")) == "portable-test"
    assert paths.provider_config.is_file()
    assert not paths.google_books_config.exists()
    # The profile source stays available as recovery data but is inactive after
    # the canonical migration marker is written.
    assert legacy_config.is_file()
    CopyLifecycleService(db, paths.data).purge()
    paths.prepare()
    migrated_db = Database(paths.database)
    config_store.migrate_legacy_settings(migrated_db, paths.google_books_config, paths._profile_google_books_config())
    assert not paths.google_books_config.exists()
    assert config_store.get(("api_keys", "google_books")) == "portable-test"
    assert legacy_config.is_file()


def test_trash_restore_and_clear_preserve_siblings_and_hide_history(tmp_path):
    data = tmp_path / "data"
    db = Database(data / "bookledger.sqlite3")
    catalog = CatalogService(db, data)
    first = catalog.create_copy(_payload(data, "First", "9780306406157"))
    sibling = catalog.create_copy(
        _payload(data, "Sibling", "9780306406157"),
        existing_book_id=catalog.duplicate_by_isbn("9780306406157")["id"],
    )
    catalog.change_status(first, "Sold")
    lifecycle = CopyLifecycleService(db, data)
    lifecycle.trash_copy(first)
    assert [row["copy_id"] for row in catalog.list_copies()] == [sibling]
    assert catalog.list_sales() == []
    assert (data / "trash" / f"{first}.jpg").is_file()
    assert lifecycle.restore_latest() == first
    assert len(catalog.list_sales()) == 1
    assert catalog.get_copy(first)["status"] == "Sold"
    assert lifecycle.trash_copy(first) is None
    assert lifecycle.clear_trash() == 1
    assert catalog.get_copy(first) is None
    assert catalog.get_copy(sibling) is not None
    assert catalog.list_sales() == []
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM book_records WHERE isbn='9780306406157'").fetchone()[0] == 1


def test_verifier_reports_missing_and_orphan_photos_without_deleting(tmp_path):
    data = tmp_path / "data"
    db = Database(data / "bookledger.sqlite3")
    catalog = CatalogService(db, data)
    copy_id = catalog.create_copy(_payload(data, "First", "9780306406157"))
    orphan = data / "photos" / "orphan.jpg"
    Image.new("RGB", (20, 20)).save(orphan)
    (data / "photos" / f"{copy_id}.jpg").unlink()
    report = VerificationService(db, data).verify()
    assert not report.ok
    assert any(f"Copy ID {copy_id}" in error for error in report.errors)
    assert orphan.is_file()


def test_copy_photos_use_canonical_names_and_retake_is_atomic(tmp_path, monkeypatch):
    data = tmp_path / "data"
    db = Database(data / "bookledger.sqlite3")
    catalog = CatalogService(db, data)
    payload = _payload(data, "First", "9780306406157")
    copy_id = catalog.create_copy(payload)
    canonical = data / "photos" / f"{copy_id}.jpg"
    original_bytes = canonical.read_bytes()
    replacement = data / "replacement.png"
    Image.new("RGB", (60, 60), "orange").save(replacement)
    staged = catalog.photos.import_and_compress(replacement)
    catalog.update_copy(copy_id, {**payload, "photo_path": str(staged)})
    assert canonical.is_file()
    assert canonical.read_bytes() != original_bytes
    assert not staged.exists()

    staged_again = catalog.photos.import_and_compress(replacement)
    monkeypatch.setattr(catalog.photos, "replace", lambda *_args: (_ for _ in ()).throw(OSError("simulated replace failure")))
    with pytest.raises(ValidationError) as exc:
        catalog.update_copy(copy_id, {**payload, "photo_path": str(staged_again)})
    assert "Photo replacement needs recovery" in exc.value.errors["photo_path"]
    assert canonical.is_file()
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM storage_operations WHERE operation='replace'").fetchone()[0] == 1


def test_trash_is_restored_in_lifo_order(tmp_path):
    data = tmp_path / "data"
    db = Database(data / "bookledger.sqlite3")
    catalog = CatalogService(db, data)
    one = catalog.create_copy(_payload(data, "One", "9780306406157"))
    two = catalog.create_copy(_payload(data, "Two", "9780140449136"))
    lifecycle = CopyLifecycleService(db, data)
    lifecycle.trash_copy(one)
    lifecycle.trash_copy(two)
    assert lifecycle.restore_latest() == two
    assert lifecycle.restore_latest() == one


def test_purge_removes_only_data_and_preserves_root_backups(tmp_path):
    root = tmp_path / "BookLedger"
    data = root / "data"
    db = Database(data / "bookledger.sqlite3")
    (data / "assets").mkdir()
    (data / "assets" / "google_books.json").write_text('{"api_key":"test"}')
    backup = root / "backups" / "keep.zip"
    backup.parent.mkdir()
    backup.write_bytes(b"keep")
    CopyLifecycleService(db, data).purge()
    assert list(data.iterdir()) == []
    assert backup.read_bytes() == b"keep"
