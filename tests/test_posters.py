import json
import sqlite3
import zipfile
from pathlib import Path

import pytest
from PIL import Image

from bookledger.db.database import Database
from bookledger.paths import AppPaths
from bookledger.services.backups import BackupService
from bookledger.services.catalog import CatalogService
from bookledger.services.lifecycle import CopyLifecycleService
from bookledger.services.photos import PhotoService
from bookledger.services.posters import PosterService, poster_price, title_for_poster
from bookledger.services import backups as backups_module


def _setup(root):
    paths = AppPaths(root)
    paths.prepare()
    db = Database(paths.database)
    catalog = CatalogService(db, paths.data)
    source = paths.data / "source.png"
    Image.new("RGB", (120, 180), "navy").save(source)
    copy_id = catalog.create_copy({
        "title": "A Test Book", "author": "An Author", "isbn": "9780306406157",
        "genre": "Science", "format": "Paperback", "condition": "Good",
        "location": "Not Specified", "price": "123.45", "photo_path": str(source),
        "publisher": "Test Press", "publication_year": "2020", "edition": "First",
        "page_count": "100", "book_details": "A short description",
    })
    return paths, db, catalog, PosterService(db, paths), copy_id


@pytest.mark.parametrize("length,expected_lines", [(25, 1), (26, 2), (50, 2)])
def test_poster_title_lengths_wrap_deterministically(length, expected_lines):
    rendered = title_for_poster("x" * length)
    assert rendered.count("\n") + 1 == expected_lines


def test_poster_title_requires_short_copy_above_50_without_changing_input():
    original = "An extremely long book title that is much longer than fifty characters and must be shortened"
    with pytest.raises(ValueError, match="shortened title is required"):
        title_for_poster(original)
    shortened = title_for_poster(original, "Short poster title")
    assert shortened == "Short poster title"
    assert len(original) > 50


def test_poster_price_uses_peso_suffix_once_and_rejects_missing_price():
    assert poster_price(12345) == "₱123.45"
    assert poster_price(12345).count("₱") == 1
    with pytest.raises(ValueError, match="valid sale price"):
        poster_price(None)


def test_schema_v7_migrates_to_poster_templates_without_touching_copy_records(tmp_path):
    paths = AppPaths(tmp_path / "portable")
    paths.prepare()
    db = Database(paths.database)
    with db.connect() as conn:
        conn.execute("INSERT INTO book_records(id,title,author,genre) VALUES(9,'Keep','Author','Science')")
        conn.execute("PRAGMA user_version=7")
        conn.execute("DROP TABLE poster_templates")
    migrated = Database(paths.database)
    with migrated.connect() as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 8
        assert conn.execute("SELECT title FROM book_records WHERE id=9").fetchone()[0] == "Keep"
        assert conn.execute("SELECT COUNT(*) FROM poster_templates").fetchone()[0] == 0


def test_template_backgrounds_presets_and_shared_discard_are_safe(tmp_path):
    paths, _db, _catalog, service, _copy_id = _setup(tmp_path / "portable")
    source = tmp_path / "background.png"
    Image.new("RGB", (600, 750), "white").save(source)
    reference, background = service.add_background(source)
    second_reference, second_background = service.add_background(source)
    assert second_background.name == "template_background_2.png"
    first = service.save_template(reference, [{"field": "Title", "x": 0.1, "y": 0.2, "w": 0.6, "h": 0.2, "font_size": 30}])
    second = service.save_template(reference, [{"field": "Price", "x": 0.2, "y": 0.8, "w": 0.3, "h": 0.1, "font_size": 24}])
    assert (first["name"], second["name"]) == ("Preset 1", "Preset 2")
    assert service.get_template(first["id"])["elements"][0]["font_size"] == 30
    service.discard_template(first["id"])
    assert background.is_file()
    service.discard_template(second["id"])
    assert not background.exists()
    assert second_background.exists()
    assert reference.startswith("assets/")
    third = service.save_template(second_reference, [])
    assert third["name"] == "Preset 3"


def test_template_rejects_nonfinite_or_out_of_bounds_geometry(tmp_path):
    _paths, _db, _catalog, service, _copy_id = _setup(tmp_path / "portable")
    source = tmp_path / "background.png"
    Image.new("RGB", (600, 750), "white").save(source)
    reference, _ = service.add_background(source)
    with pytest.raises(ValueError, match="fit inside the canvas"):
        service.save_template(reference, [{"field": "Title", "x": 0.8, "y": 0.1, "w": 0.4, "h": 0.2}])
    with pytest.raises(ValueError, match="finite"):
        service.save_template(reference, [{"field": "Title", "x": float("nan"), "y": 0.1, "w": 0.4, "h": 0.2}])


def test_background_falls_back_to_managed_data_when_application_assets_is_not_a_directory(tmp_path):
    root = tmp_path / "portable"
    (root / "assets").parent.mkdir(parents=True)
    (root / "assets").write_text("blocks the application asset directory", encoding="utf-8")
    paths = AppPaths(root)
    paths.prepare()
    service = PosterService(Database(paths.database), paths)
    source = tmp_path / "background.jpg"
    Image.new("RGB", (100, 100), "white").save(source)
    reference, destination = service.add_background(source)
    assert reference.startswith("data/poster_backgrounds/")
    assert destination.parent == paths.poster_background_fallback


def test_render_exports_canonical_copy_png_at_social_size(tmp_path):
    paths, _db, catalog, service, copy_id = _setup(tmp_path / "portable")
    source = tmp_path / "poster-bg.png"
    Image.new("RGB", (600, 750), "white").save(source)
    reference, _ = service.add_background(source)
    template = service.save_template(reference, [
        {"field": "Title", "x": 0.1, "y": 0.1, "w": 0.7, "h": 0.2, "font_size": 30},
        {"field": "Price", "x": 0.1, "y": 0.8, "w": 0.4, "h": 0.1, "font_size": 30},
        {"field": "Photo", "x": 0.5, "y": 0.3, "w": 0.3, "h": 0.4, "font_size": 24},
    ])
    row = catalog.get_copy(copy_id)
    rendered = service.render(template, row)
    assert min(rendered.size) >= 1080
    target = service.export(template, row)
    assert target == paths.posters / f"BL-{copy_id:06d}.png"
    with Image.open(target) as poster:
        assert poster.format == "PNG"
        assert min(poster.size) >= 1080


def test_backup_includes_managed_fallback_backgrounds(tmp_path):
    root = tmp_path / "portable"
    (root / "assets").parent.mkdir(parents=True)
    (root / "assets").write_text("not an assets directory", encoding="utf-8")
    paths, db, _catalog, service, _copy_id = _setup(root)
    source = tmp_path / "background.png"
    Image.new("RGB", (400, 500), "white").save(source)
    reference, destination = service.add_background(source)
    assert reference.startswith("data/poster_backgrounds/")
    template = service.save_template(reference, [])
    backup = BackupService(db, paths.data, paths.backups, paths.provider_config)
    archive = backup.create_backup()
    valid, reason = backup.verify_archive(archive)
    assert valid, reason
    with zipfile.ZipFile(archive) as snapshot:
        assert f"data/poster_backgrounds/{destination.name}" in snapshot.namelist()
    service.discard_template(template["id"])
    backup.restore_backup(archive)
    assert destination.is_file()
    assert service.list_templates()[0]["background_ref"] == reference


def test_restore_remaps_application_background_to_fallback_when_assets_are_read_only(tmp_path, monkeypatch):
    root = tmp_path / "portable"
    paths, db, _catalog, service, _copy_id = _setup(root)
    source = tmp_path / "background.png"
    Image.new("RGB", (400, 500), "white").save(source)
    reference, original = service.add_background(source)
    template = service.save_template(reference, [])
    backup = BackupService(db, paths.data, paths.backups, paths.provider_config)
    archive = backup.create_backup()
    real_mkstemp = backups_module.tempfile.mkstemp

    def deny_asset_writes(*args, **kwargs):
        if Path(kwargs.get("dir", "")).resolve() == (root / "assets").resolve():
            raise PermissionError("simulated read-only application assets")
        return real_mkstemp(*args, **kwargs)

    monkeypatch.setattr(backups_module.tempfile, "mkstemp", deny_asset_writes)
    backup.restore_backup(archive)
    restored = service.get_template(template["id"])
    assert restored["background_ref"].startswith("data/poster_backgrounds/")
    assert service.resolve_background(restored["background_ref"]).is_file()
    assert original.is_file()


def test_backup_restore_includes_templates_backgrounds_and_posters_preserving_unrelated_files(tmp_path):
    root = tmp_path / "portable"
    paths, db, catalog, service, copy_id = _setup(root)
    bg_source = tmp_path / "poster-bg.png"
    Image.new("RGB", (600, 750), "white").save(bg_source)
    reference, background = service.add_background(bg_source)
    template = service.save_template(reference, [{"field": "Title", "x": 0.1, "y": 0.1, "w": 0.7, "h": 0.2, "font_size": 30}])
    catalog.get_copy(copy_id)
    poster_path = paths.posters / f"BL-{copy_id:06d}.png"
    Image.new("RGB", (1080, 1350), "white").save(poster_path)
    unrelated_asset = root / "assets" / "icon.ico"
    unrelated_asset.write_bytes(b"bundled icon")
    unrelated_poster = paths.posters / "notes.txt"
    unrelated_poster.write_text("keep", encoding="utf-8")
    backup = BackupService(db, paths.data, paths.backups, paths.provider_config)
    archive_path = backup.create_backup()
    with zipfile.ZipFile(archive_path) as archive:
        names = set(archive.namelist())
        assert f"application_assets/{background.name}" in names
        assert f"posters/{poster_path.name}" in names
        assert "data/poster_backgrounds" not in names
        snap_db = sqlite3.connect(":memory:")
        snap_db.deserialize(archive.read("data/bookledger.sqlite3"))
        assert snap_db.execute("SELECT name FROM poster_templates").fetchone()[0] == template["name"]
        snap_db.close()
    service.discard_template(template["id"])
    poster_path.unlink()
    recovery = backup.restore_backup(archive_path)
    assert background.is_file()
    assert poster_path.is_file()
    assert unrelated_asset.read_bytes() == b"bundled icon"
    assert unrelated_poster.read_text(encoding="utf-8") == "keep"
    assert service.list_templates()[0]["name"] == "Preset 1"
    assert recovery.is_file()


def test_purge_removes_only_managed_poster_files(tmp_path):
    root = tmp_path / "portable"
    paths, db, _catalog, service, _copy_id = _setup(root)
    bg_source = tmp_path / "poster-bg.png"
    Image.new("RGB", (100, 100), "white").save(bg_source)
    _reference, background = service.add_background(bg_source)
    generated = paths.posters / "BL-000001.png"
    Image.new("RGB", (10, 10), "white").save(generated)
    unrelated_asset = root / "assets" / "keep.json"
    unrelated_asset.write_text("{}", encoding="utf-8")
    unrelated_output = paths.posters / "keep.txt"
    unrelated_output.write_text("keep", encoding="utf-8")
    CopyLifecycleService(db, paths.data).purge()
    assert not background.exists()
    assert not generated.exists()
    assert unrelated_asset.is_file()
    assert unrelated_output.read_text(encoding="utf-8") == "keep"

