import json
import sqlite3
import threading
import uuid
import zipfile

import pytest
from PIL import Image

from bookledger.db.database import Database
from bookledger.services.backups import BackupService
from bookledger.services.catalog import CatalogService


@pytest.fixture
def setup(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    db = Database(data / "bookledger.sqlite3")
    source = data / "photo.png"
    Image.new("RGB", (100, 100), "white").save(source)
    payload = {
        "title": "Test Book", "author": "Test Author", "isbn": "9780306406157",
        "genre": "Science", "format": "Paperback", "condition": "Good",
        "location": "", "price": "500", "photo_path": str(source), "srp": "600",
        "book_details": "A synopsis", "publisher": "Test Press", "publication_year": "2020",
        "edition": "1st", "page_count": "100", "metadata_source": "Test", "metadata_status": "Retrieved",
    }
    return tmp_path, data, db, CatalogService(db), payload, source


def test_copies_receive_immutable_unique_uuids_and_keep_display_codes(setup):
    _, _, db, catalog, payload, _ = setup
    first_id = catalog.create_copy(payload)
    first = catalog.get_copy(first_id)
    first_uuid = uuid.UUID(first["copy_uuid"])
    assert first["copy_code"] == f"BL-{first_id:06d}"
    catalog.update_copy(first_id, {**payload, "price": "515"})
    catalog.change_status(first_id, "Sold")
    assert catalog.get_copy(first_id)["copy_uuid"] == str(first_uuid)

    second_id = catalog.create_copy({**payload, "isbn": None, "title": "Another"})
    second = catalog.get_copy(second_id)
    assert uuid.UUID(second["copy_uuid"])
    assert second["copy_uuid"] != str(first_uuid)
    with db.connect() as conn:
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            conn.execute("UPDATE copies SET copy_uuid=? WHERE id=?", (str(uuid.uuid4()), first_id))


def test_backup_contains_config_assets_manifest_and_unique_names(setup):
    root, data, db, catalog, payload, _ = setup
    copy_id = catalog.create_copy(payload)
    (data / "assets").mkdir()
    (data / "assets" / "keep.json").write_text('{"kept":true}', encoding="utf-8")
    config = root / "config.json"
    config.write_text(json.dumps({"api_keys": {"google_books": "test-secret"}, "preferences": {"locations": ["Shelf"]}}), encoding="utf-8")
    backups = BackupService(db, data, root / "backups", config)

    first = backups.create_backup()
    second = backups.create_backup()
    assert first != second
    assert first.exists() and second.exists()
    valid, message = backups.verify_archive(first)
    assert valid, message
    with zipfile.ZipFile(first) as archive:
        names = set(archive.namelist())
        assert "config.json" in names
        assert "data/bookledger.sqlite3" in names
        assert "data/assets/keep.json" in names
        assert f"data/photos/{copy_id}.jpg" in names
        assert not any(".staging" in name for name in names)
        assert "manifest.json" in names
        snapshot = json.loads(archive.read("config.json"))
        assert snapshot["api_keys"]["google_books"] == "test-secret"


def test_restore_replaces_snapshot_state_and_preserves_recovery_point(setup):
    root, data, db, catalog, payload, _ = setup
    config = root / "config.json"
    config.write_text('{"preferences":{"locations":["Snapshot Shelf"]}}', encoding="utf-8")
    copy_id = catalog.create_copy(payload)
    catalog.change_status(copy_id, "Sold")
    catalog.change_status(copy_id, "Available", void_reason="Returned Order")
    backups = BackupService(db, data, root / "backups", config)
    archive = backups.create_backup()
    original_uuid = catalog.get_copy(copy_id)["copy_uuid"]

    catalog.create_copy({**payload, "title": "Created after snapshot", "isbn": None})
    config.write_text('{"preferences":{"locations":["Later Shelf"]}}', encoding="utf-8")
    recovery = backups.restore_backup(archive)

    rows = catalog.list_copies()
    assert [row["title"] for row in rows] == ["Test Book"]
    assert rows[0]["copy_uuid"] == original_uuid
    history = catalog.get_copy_details(copy_id)["sale_history"]
    assert len(history) == 1
    assert history[0]["void_reason"] == "Returned Order"
    assert history[0]["voided_at"]
    assert json.loads(config.read_text(encoding="utf-8"))["preferences"]["locations"] == ["Snapshot Shelf"]
    assert recovery.is_file()
    assert backups.verify_archive(recovery)[0]


def test_corrupt_and_unsafe_archives_are_rejected_before_restore(setup):
    root, data, db, catalog, payload, _ = setup
    catalog.create_copy(payload)
    backups = BackupService(db, data, root / "backups")
    good = backups.create_backup()
    bad = root / "unsafe.zip"
    with zipfile.ZipFile(good) as source, zipfile.ZipFile(bad, "w") as target:
        for item in source.infolist():
            target.writestr(item, source.read(item.filename))
        target.writestr("data/photos/../../outside.txt", b"bad")
    valid, reason = backups.verify_archive(bad)
    assert not valid
    assert "unsafe" in reason.lower()

    before = len(catalog.list_copies())
    with pytest.raises(ValueError, match="verification failed"):
        backups.restore_backup(bad)
    assert len(catalog.list_copies()) == before


def test_interrupted_restore_recovery_restores_prior_components(tmp_path):
    root = tmp_path
    data = root / "data"
    data.mkdir()
    active = data / "photos"
    active.mkdir()
    (active / "new.jpg").write_bytes(b"new")
    work = root / ".bookledger-restore-interrupted"
    (work / "old-photos").mkdir(parents=True)
    (work / "old-photos" / "old.jpg").write_bytes(b"old")
    (work / "stage" / "data").mkdir(parents=True)
    (work / "stage" / "data" / "photos").mkdir()
    (work / "restore.json").write_text(json.dumps({"version": 1, "had_old": {"database": False, "photos": True, "trash": False, "assets": False, "config": False}}), encoding="utf-8")

    recovered = BackupService.recover_interrupted_restore(root)
    assert recovered == (work.name,)
    assert [path.name for path in active.iterdir()] == ["old.jpg"]
    assert not work.exists()


def test_empty_library_snapshot_restores_as_an_empty_library(setup):
    root, data, db, catalog, payload, _ = setup
    backups = BackupService(db, data, root / "backups")
    archive = backups.create_backup()
    catalog.create_copy(payload)
    backups.restore_backup(archive)
    assert catalog.list_copies() == []
    assert backups.latest_recovery_point and backups.latest_recovery_point.is_file()


def test_database_operation_guard_blocks_other_connections_until_released(setup):
    _, _, db, _, _, _ = setup
    started = threading.Event()
    acquired = threading.Event()

    def connect_after_guard():
        started.set()
        with db.connect():
            acquired.set()

    with db.operation_guard():
        worker = threading.Thread(target=connect_after_guard)
        worker.start()
        assert started.wait(2)
        assert not acquired.wait(0.05)
    assert acquired.wait(2)
    worker.join(timeout=2)


def test_failed_component_activation_rolls_back_library_and_keeps_recovery(setup, monkeypatch):
    root, data, db, catalog, payload, _ = setup
    first_id = catalog.create_copy(payload)
    original_uuid = catalog.get_copy(first_id)["copy_uuid"]
    backups = BackupService(db, data, root / "backups")
    archive = backups.create_backup()
    catalog.create_copy({**payload, "title": "Current library", "isbn": None})
    replace = type(data).replace
    failed = {"done": False}

    def fail_once(source, destination):
        if not failed["done"] and source.name == "photos" and "stage" in source.parts:
            failed["done"] = True
            raise OSError("simulated activation failure")
        return replace(source, destination)

    monkeypatch.setattr(type(data), "replace", fail_once)
    with pytest.raises(OSError, match="simulated activation failure"):
        backups.restore_backup(archive)
    monkeypatch.setattr(type(data), "replace", replace)
    rows = catalog.list_copies()
    assert {row["title"] for row in rows} == {"Test Book", "Current library"}
    assert catalog.get_copy(first_id)["copy_uuid"] == original_uuid
    assert backups.latest_recovery_point and backups.latest_recovery_point.is_file()
