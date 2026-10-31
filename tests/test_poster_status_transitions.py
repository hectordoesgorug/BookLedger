from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from bookledger.ui import poster_designer


class _PosterService:
    def __init__(self, output, *, failure=False):
        self.output = output
        self.failure = failure
        self.exports = 0

    def list_templates(self):
        return [{"id": 1, "background_ref": "assets/template_background_1.png", "elements": []}]

    def resolve_background(self, _reference):
        return Path("background.png")

    def export(self, *_args, **_kwargs):
        self.exports += 1
        if self.failure:
            raise OSError("export failed")
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self.output.write_bytes(b"poster")
        return self.output


class _Catalog:
    def __init__(self, status):
        self.row = {"copy_id": 7, "copy_code": "BL-000007", "title": "Book", "status": status}
        self.status_changes = []

    def get_copy(self, _copy_id):
        return dict(self.row)

    def change_status(self, copy_id, status):
        self.status_changes.append((copy_id, status))
        self.row["status"] = status


def _run(monkeypatch, tmp_path, status, *, confirms=(), failure=False, existing=None):
    output = tmp_path / "posters" / "BL-000007.png"
    if existing is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(existing)
    service = _PosterService(output, failure=failure)
    catalog = _Catalog(status)
    calls = []
    errors = []
    responses = iter(confirms)
    monkeypatch.setattr(poster_designer.messagebox, "askyesno", lambda *_args, **_kwargs: next(responses, False))
    monkeypatch.setattr(poster_designer.messagebox, "showinfo", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(poster_designer.messagebox, "showerror", lambda title, message, **_kwargs: errors.append((title, message)))
    monkeypatch.setattr(poster_designer.simpledialog, "askstring", lambda *_args, **_kwargs: None)
    saved = poster_designer.create_poster_for_copy(
        SimpleNamespace(winfo_exists=lambda: True), service=service, catalog=catalog,
        paths=SimpleNamespace(posters=output.parent), config_store=SimpleNamespace(get=lambda _key: 1),
        copy_id=7, on_activity=lambda event, identifier: calls.append((event, identifier)),
    )
    return saved, output, service, catalog, calls, errors


def test_available_copy_becomes_listed_only_after_successful_export(monkeypatch, tmp_path):
    saved, output, service, catalog, events, _errors = _run(monkeypatch, tmp_path, "Available")
    assert saved == output
    assert service.exports == 1
    assert catalog.row["status"] == "Listed"
    assert catalog.status_changes == [(7, "Listed")]
    assert events == [("inventory_status_changed", 7), ("poster_generated", 7)]


def test_listed_copy_replaces_existing_poster_without_status_confirmation(monkeypatch, tmp_path):
    saved, output, service, catalog, events, _errors = _run(
        monkeypatch, tmp_path, "Listed", confirms=(True,), existing=b"old poster"
    )
    assert saved == output
    assert output.read_bytes() == b"poster"
    assert service.exports == 1
    assert catalog.row["status"] == "Listed"
    assert catalog.status_changes == []
    assert events == [("poster_replaced", 7)]


def test_not_for_sale_requires_confirmation_then_becomes_listed(monkeypatch, tmp_path):
    saved, _output, service, catalog, events, _errors = _run(
        monkeypatch, tmp_path, "Not for Sale", confirms=(True,)
    )
    assert saved is not None
    assert service.exports == 1
    assert catalog.row["status"] == "Listed"
    assert catalog.status_changes == [(7, "Listed")]
    assert events == [("inventory_status_changed", 7), ("poster_generated", 7)]


def test_not_for_sale_decline_or_failed_export_preserves_status_and_poster(monkeypatch, tmp_path):
    declined = _run(monkeypatch, tmp_path / "declined", "Not for Sale", confirms=(False,))
    assert declined[0] is None
    assert declined[2].exports == 0
    assert declined[3].row["status"] == "Not for Sale"

    failed = _run(monkeypatch, tmp_path / "failed", "Not for Sale", confirms=(True,), failure=True)
    assert failed[0] is None
    assert failed[2].exports == 1
    assert failed[3].row["status"] == "Not for Sale"
    assert failed[4] == [("poster_generation_failed", 7)]


def test_declining_existing_poster_replacement_preserves_not_for_sale(monkeypatch, tmp_path):
    saved, output, service, catalog, events, _errors = _run(
        monkeypatch, tmp_path, "Not for Sale", confirms=(True, False), existing=b"old poster"
    )
    assert saved is None
    assert output.read_bytes() == b"old poster"
    assert service.exports == 0
    assert catalog.row["status"] == "Not for Sale"
    assert events == []


def test_sold_copy_is_rejected_before_template_or_export(monkeypatch, tmp_path):
    saved, _output, service, catalog, events, errors = _run(monkeypatch, tmp_path, "Sold")
    assert saved is None
    assert service.exports == 0
    assert catalog.row["status"] == "Sold"
    assert catalog.status_changes == []
    assert events == []
    assert errors and "Sold" in errors[0][1]


def test_available_export_failure_retains_available_status(monkeypatch, tmp_path):
    saved, _output, service, catalog, events, _errors = _run(
        monkeypatch, tmp_path, "Available", failure=True
    )
    assert saved is None
    assert service.exports == 1
    assert catalog.row["status"] == "Available"
    assert catalog.status_changes == []
    assert events == [("poster_generation_failed", 7)]


def test_real_catalog_status_changes_only_after_poster_is_written(monkeypatch, tmp_path):
    from bookledger.db.database import Database
    from bookledger.paths import AppPaths
    from bookledger.services.catalog import CatalogService
    from bookledger.services.posters import PosterService

    paths = AppPaths(tmp_path / "BookLedger")
    paths.prepare()
    db = Database(paths.database)
    catalog = CatalogService(db, paths.data)
    photo = paths.data / "copy.jpg"
    background = tmp_path / "poster-background.png"
    Image.new("RGB", (80, 100), "navy").save(photo)
    Image.new("RGB", (400, 500), "white").save(background)
    copy_id = catalog.create_copy({
        "title": "Poster Integration", "author": "Test Author", "isbn": "9780306406157",
        "genre": "Science", "format": "Paperback", "condition": "Good",
        "location": "Not Specified", "price": "50", "photo_path": str(photo),
    })
    service = PosterService(db, paths)
    reference, _saved_background = service.add_background(background)
    service.save_template(reference, [])
    monkeypatch.setattr(poster_designer.messagebox, "askyesno", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(poster_designer.messagebox, "showinfo", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(poster_designer.messagebox, "showerror", lambda *_args, **_kwargs: pytest.fail("poster generation should succeed"))

    saved = poster_designer.create_poster_for_copy(
        SimpleNamespace(winfo_exists=lambda: True), service=service, catalog=catalog,
        paths=paths, config_store=None, copy_id=copy_id,
    )

    assert saved == paths.posters / f"BL-{copy_id:06d}.png"
    assert saved.is_file()
    assert catalog.get_copy(copy_id)["status"] == "Listed"
