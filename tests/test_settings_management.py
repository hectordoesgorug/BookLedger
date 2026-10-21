from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from types import SimpleNamespace

from bookledger import app as app_module
from bookledger.app import BookLedgerApp
from bookledger.config_store import AppConfigStore


class Value:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


def test_google_books_key_save_and_remove_preserve_other_configuration(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"version": 1, "metadata_providers": {"enabled": ["open_library"]}, "custom": {"x": 1}}), encoding="utf-8")
    subject = SimpleNamespace(
        config_store=AppConfigStore(config_path),
        google_books_key_var=Value("new-key"),
        google_books_api_status=Value(),
        _apply_google_books_key=lambda key: setattr(subject, "applied_key", key),
    )

    assert BookLedgerApp._save_google_books_key(subject)
    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved == {
        "version": 1,
        "metadata_providers": {"enabled": ["open_library"]},
        "custom": {"x": 1},
        "api_keys": {"google_books": "new-key"},
    }
    assert subject.applied_key == "new-key"

    monkeypatch.setattr(app_module.messagebox, "askyesno", lambda *_args, **_kwargs: True)
    BookLedgerApp._remove_google_books_key(subject)
    removed = json.loads(config_path.read_text(encoding="utf-8"))
    assert removed["api_keys"] == {}
    assert removed["custom"] == {"x": 1}
    assert removed["metadata_providers"] == {"enabled": ["open_library"]}
    assert subject.google_books_key_var.get() == ""
    assert subject.applied_key == ""


def test_google_books_key_load_uses_canonical_configuration(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({"api_keys": {"google_books": "synthetic-key"}}), encoding="utf-8"
    )
    subject = SimpleNamespace(config_store=AppConfigStore(config_path))

    assert BookLedgerApp._load_google_books_key(subject) == "synthetic-key"


def test_google_books_remove_cancel_and_invalid_config_leave_file_unchanged(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    original = '{"api_keys":{"google_books":"keep-me"},"unrelated":true}\n'
    config_path.write_text(original, encoding="utf-8")
    subject = SimpleNamespace(
        config_store=AppConfigStore(config_path),
        google_books_key_var=Value("keep-me"),
        google_books_api_status=Value(),
        _apply_google_books_key=lambda _key: None,
    )
    monkeypatch.setattr(app_module.messagebox, "askyesno", lambda *_args, **_kwargs: False)
    BookLedgerApp._remove_google_books_key(subject)
    assert config_path.read_text(encoding="utf-8") == original

    config_path.write_text("not json", encoding="utf-8")
    subject.google_books_key_var.set("attempted-change")
    assert not BookLedgerApp._save_google_books_key(subject)
    # The configuration service preserves a malformed canonical file and, with no
    # fallback configured, reports the write failure without replacing it.
    assert config_path.read_text(encoding="utf-8") == "not json"
    assert "Could not save" in subject.google_books_api_status.get()


def test_export_inventory_csv_is_utf8_read_only_and_reports_cancellation(tmp_path, monkeypatch):
    copies = [
        {
            "copy_id": 7, "copy_code": "BL-000007", "copy_number": 1, "title": "Café",
            "author": "A. Writer", "isbn": "9780000000001", "genre": "Fiction",
            "publisher": "Press", "publication_year": 2024, "edition": None,
            "page_count": 50, "book_details": "Notes", "srp_minor": 55000, "format": "Paperback",
            "condition": "Good", "location": "Shelf", "price_minor": 12345, "status": "Sold",
            "metadata_source": "Open Library", "metadata_status": "Retrieved",
        },
    ]
    calls = []
    destination = tmp_path / "inventory.csv"
    subject = SimpleNamespace(
        paths=SimpleNamespace(root=tmp_path),
        catalog=SimpleNamespace(list_copies=lambda: calls.append("read") or copies),
        status_var=Value(),
    )
    monkeypatch.setattr(app_module.filedialog, "asksaveasfilename", lambda **_kwargs: str(destination))
    monkeypatch.setattr(app_module.messagebox, "showinfo", lambda *args, **_kwargs: calls.append(args[0]))

    BookLedgerApp.export_inventory_csv(subject)

    with destination.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert rows[0]["Title"] == "Café"
    assert rows[0]["Status"] == "Sold"
    assert rows[0]["Price (PHP)"] == "123.45"
    assert rows[0]["SRP (PHP)"] == "550.00"
    assert calls == ["read", "CSV export complete"]
    assert "1 inventory copies" in subject.status_var.get()

    calls.clear()
    subject.catalog.list_copies = lambda: (_ for _ in ()).throw(AssertionError("cancel should not read inventory"))
    monkeypatch.setattr(app_module.filedialog, "asksaveasfilename", lambda **_kwargs: "")
    BookLedgerApp.export_inventory_csv(subject)
    assert calls == []


def test_export_inventory_csv_reports_file_errors(tmp_path, monkeypatch):
    errors = []
    subject = SimpleNamespace(
        paths=SimpleNamespace(root=tmp_path),
        catalog=SimpleNamespace(list_copies=lambda: []),
        status_var=Value(),
    )
    monkeypatch.setattr(app_module.filedialog, "asksaveasfilename", lambda **_kwargs: str(tmp_path / "blocked.csv"))
    monkeypatch.setattr(app_module.messagebox, "showerror", lambda *args, **_kwargs: errors.append(args))
    monkeypatch.setattr("builtins.open", lambda *_args, **_kwargs: (_ for _ in ()).throw(PermissionError("blocked")))

    BookLedgerApp.export_inventory_csv(subject)

    assert errors and errors[0][0] == "CSV export failed"
    assert "blocked" in errors[0][1]


def test_optional_logging_persists_toggle_and_clear_keeps_file(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    config_store = AppConfigStore(config_path)
    path = tmp_path / "log.txt"
    logger = logging.getLogger("bookledger.optional_diagnostics")
    subject = SimpleNamespace(
        config_store=config_store,
        paths=SimpleNamespace(root=tmp_path),
        _optional_logger=logger,
        _logging_enabled=False,
        logging_var=Value(True),
        logging_status_var=Value(),
        view_log_button=SimpleNamespace(configure=lambda **_kwargs: None),
        clear_log_button=SimpleNamespace(configure=lambda **_kwargs: None),
    )
    subject._configure_optional_logging = lambda enabled: BookLedgerApp._configure_optional_logging(subject, enabled)
    monkeypatch.setattr(app_module.messagebox, "askyesno", lambda *_args, **_kwargs: True)
    try:
        BookLedgerApp._toggle_logging(subject)
        assert subject._logging_enabled is True
        assert path.is_file()
        logger.info("test diagnostic")
        assert config_store.get(("logging", "enabled")) is True
        assert "test diagnostic" in path.read_text(encoding="utf-8")

        BookLedgerApp.clear_log(subject)
        assert path.is_file()
        assert path.read_text(encoding="utf-8") == ""

        subject.logging_var.set(False)
        BookLedgerApp._toggle_logging(subject)
        before = path.read_text(encoding="utf-8")
        logger.info("must not be written")
        assert path.read_text(encoding="utf-8") == before
        assert subject.view_log_button is not None and subject.clear_log_button is not None
        assert config_store.get(("logging", "enabled")) is False
    finally:
        BookLedgerApp._configure_optional_logging(subject, False)


def test_logging_disabled_by_default_and_configuration_failure_is_nonfatal():
    class BrokenConfiguration:
        def get(self, *_args, **_kwargs):
            raise OSError("unavailable")

    assert not BookLedgerApp._read_logging_enabled(SimpleNamespace(config_store=BrokenConfiguration()))
