from __future__ import annotations

import tkinter as tk
from dataclasses import replace
import re
from types import SimpleNamespace
from tkinter import ttk

import pytest

from bookledger import app as app_module
from bookledger.app import BookLedgerApp
from bookledger.provider_registry import PROVIDER_REGISTRY
from bookledger.services.metadata_contract import MetadataResult
from bookledger.ui.provider_diagnostic import (
    DIAGNOSTIC_TIMEOUT_SECONDS,
    FIELD_DEFINITIONS,
    FIELD_COLORS,
    MetadataProviderTestDialog,
    TIME_FAST_COLOR,
    TIME_SLOW_COLOR,
    diagnostic_field_statuses,
    diagnostic_overall_status,
    elapsed_color,
)


@pytest.fixture
def tk_root():
    try:
        root = tk.Tk()
        root.withdraw()
    except tk.TclError as exc:
        pytest.skip(f"Tk UI tests require a display: {exc}")
    yield root
    try:
        root.destroy()
    except tk.TclError:
        pass


@pytest.fixture
def dialog(tk_root):
    widget = MetadataProviderTestDialog(tk_root)
    yield widget
    try:
        widget.destroy()
    except tk.TclError:
        pass


class DeferredThread:
    instances = []

    def __init__(self, *, target, **_kwargs):
        self.target = target
        self.started = False
        self.instances.append(self)

    def start(self):
        self.started = True


class ImmediateThread:
    def __init__(self, *, target, **_kwargs):
        self.target = target

    def start(self):
        self.target()


def _walk_widgets(widget):
    for child in widget.winfo_children():
        yield child
        yield from _walk_widgets(child)


def test_settings_exposes_button_that_opens_the_diagnostic(tk_root, monkeypatch):
    class SettingsHarness:
        _build_metadata_sources = BookLedgerApp._build_metadata_sources
        _provider_drag_start = BookLedgerApp._provider_drag_start
        _provider_drag_motion = BookLedgerApp._provider_drag_motion
        _provider_drag_end = BookLedgerApp._provider_drag_end
        _reorder_provider_rows = BookLedgerApp._reorder_provider_rows

    opened = []
    harness = SettingsHarness()
    harness.workspace = ttk.Frame(tk_root)
    harness.provider_settings = SimpleNamespace(
        enabled={descriptor.id: False for descriptor in PROVIDER_REGISTRY},
        order=[descriptor.id for descriptor in PROVIDER_REGISTRY],
    )
    harness.provider_settings_store = SimpleNamespace(warning=None, active_path="config.json")
    harness.open_isbn_lookup_test = lambda: opened.append("opened")
    harness._save_provider_settings = lambda: None
    harness._restore_provider_defaults = lambda: None

    BookLedgerApp._build_metadata_sources(harness)
    button = next(
        child for child in _walk_widgets(harness.workspace)
        if isinstance(child, ttk.Button) and child.cget("text") == "ISBN Lookup Test"
    )
    button.invoke()

    assert opened == ["opened"]
    assert all(value is False for value in harness.provider_settings.enabled.values())


def test_app_opens_diagnostic_with_existing_api_key_without_saving_settings(monkeypatch):
    calls = []
    subject = SimpleNamespace(_load_google_books_key=lambda: "existing-key")

    def fake_dialog(parent, *, google_books_api_key):
        calls.append((parent, google_books_api_key))
        return "dialog"

    monkeypatch.setattr(app_module, "MetadataProviderTestDialog", fake_dialog)

    result = BookLedgerApp.open_isbn_lookup_test(subject)

    assert result == "dialog"
    assert calls == [(subject, "existing-key")]


def test_dialog_lists_registered_providers_even_when_normal_lookup_disables_them(dialog):
    assert tuple(dialog.provider_combo.cget("values")) == tuple(
        descriptor.name for descriptor in PROVIDER_REGISTRY
    )


def test_provider_change_clears_isbn_field_and_previous_results(dialog):
    dialog.isbn_var.set("9780553290998")
    dialog.overall_status_var.set("Completed")
    dialog.fetch_time_var.set("2.15 seconds")
    dialog._field_status_vars["Title"].set("OK")
    dialog.provider_var.set(dialog.provider_combo.cget("values")[1])

    dialog._provider_changed()

    assert dialog.isbn_var.get() == ""
    assert dialog.overall_status_var.get() == "Ready"
    assert dialog.fetch_time_var.get() == "—"
    assert all(var.get() == "—" for var in dialog._field_status_vars.values())


def test_empty_isbn_shows_validation_without_starting_a_worker(dialog, monkeypatch):
    DeferredThread.instances = []
    monkeypatch.setattr("bookledger.ui.provider_diagnostic.threading.Thread", DeferredThread)

    dialog._start_test()

    assert "Enter an ISBN" in dialog.validation_var.get()
    assert DeferredThread.instances == []
    assert dialog.overall_status_var.get() == "Ready"


def test_clear_resets_isbn_statuses_overall_status_and_fetch_time(dialog):
    dialog.isbn_var.set("9780553290998")
    dialog.overall_status_var.set("Partial data")
    dialog.fetch_time_var.set("4.22 seconds")
    for var in dialog._field_status_vars.values():
        var.set("No Data")

    dialog.clear()

    assert dialog.isbn_var.get() == ""
    assert dialog.overall_status_var.get() == "Ready"
    assert dialog.fetch_time_var.get() == "—"
    assert all(var.get() == "—" for var in dialog._field_status_vars.values())


def test_test_disables_controls_and_prevents_duplicate_return_submissions(dialog, monkeypatch):
    DeferredThread.instances = []
    monkeypatch.setattr("bookledger.ui.provider_diagnostic.threading.Thread", DeferredThread)
    dialog.isbn_var.set("9780553290998")

    dialog._start_test()
    dialog._start_test()

    assert dialog.overall_status_var.get() == "Retrieving data"
    assert dialog._block_enter_submission() == "break"
    assert len(DeferredThread.instances) == 1
    assert str(dialog.test_button.cget("state")) == "disabled"
    assert str(dialog.clear_button.cget("state")) == "disabled"
    assert str(dialog.close_button.cget("state")) == "disabled"
    assert str(dialog.isbn_entry.cget("state")) == "disabled"
    assert str(dialog.provider_combo.cget("state")) == "disabled"

    dialog._request_close()  # This is also the WM_DELETE_WINDOW handler.
    assert dialog.winfo_exists()


def test_timeout_reenables_dialog_and_ignores_late_worker_result(dialog, monkeypatch):
    DeferredThread.instances = []
    monkeypatch.setattr("bookledger.ui.provider_diagnostic.threading.Thread", DeferredThread)
    dialog.isbn_var.set("9780553290998")
    dialog._start_test()
    operation_id = dialog._operation_id
    descriptor = dialog._providers_by_name[dialog.provider_var.get()]

    dialog._finish_timeout(operation_id, descriptor)

    assert dialog.overall_status_var.get() == "Timeout"
    assert str(dialog.test_button.cget("state")) == "normal"
    assert str(dialog.close_button.cget("state")) == "normal"
    DeferredThread.instances[0].target()
    dialog._poll_worker_results()
    assert dialog.overall_status_var.get() == "Timeout"


def test_close_button_closes_dialog_when_idle(dialog):
    dialog.close_button.invoke()
    assert not dialog.winfo_exists()


def test_nine_display_fields_use_canonical_contract_names():
    assert FIELD_DEFINITIONS == (
        ("Title", "title"),
        ("Author", "author"),
        ("Genre", "genre"),
        ("Publisher", "publisher"),
        ("Year", "publication_year"),
        ("Edition", "edition"),
        ("Pages", "page_count"),
        ("SRP", "srp"),
        ("Book Details", "book_details"),
    )


def test_field_statuses_distinguish_returned_missing_and_unsupported_fields():
    result = MetadataResult("Retrieved", {
        "title": "A Title", "author": "  ", "page_count": 0, "book_details": "Summary",
    })

    statuses = diagnostic_field_statuses(result, {"title", "author", "page_count", "book_details"})

    assert statuses == {
        "Title": "OK", "Author": "No Data", "Genre": "N/A", "Publisher": "N/A",
        "Year": "N/A", "Edition": "N/A", "Pages": "OK", "SRP": "N/A",
        "Book Details": "OK",
    }
    assert "A Title" not in statuses.values()
    assert FIELD_COLORS["OK"] != FIELD_COLORS["No Data"]
    assert FIELD_COLORS["N/A"] != FIELD_COLORS["No Data"]


@pytest.mark.parametrize(
    ("result", "capabilities", "expected"),
    [
        (MetadataResult("Retrieved", {"title": "X", "author": "Y"}), {"title", "author"}, "Completed"),
        (MetadataResult("Retrieved", {"title": "X"}), {"title", "author"}, "Partial data"),
        (MetadataResult("No data", {}, record_found=True), {"title"}, "Partial data"),
        (MetadataResult("No data", {}, record_found=False), {"title"}, "ISBN not found"),
        (MetadataResult("Lookup failed", {}, failure_kind="timeout"), {"title"}, "Timeout"),
        (MetadataResult("Lookup failed", {}, failure_kind="provider"), {"title"}, "HTTP error"),
        (MetadataResult("Lookup failed", {}, failure_kind="unexpected"), {"title"}, "Lookup error"),
    ],
)
def test_overall_statuses_follow_the_approved_result_categories(result, capabilities, expected):
    assert diagnostic_overall_status(result, capabilities) == expected


def test_only_selected_registered_adapter_runs_and_its_instance_gets_five_second_budget(dialog, monkeypatch):
    calls = []
    factories = []

    class StubProvider:
        timeout = 2.5

        def lookup(self, _isbn):
            calls.append("lookup")
            return MetadataResult("Retrieved", {"title": "Secret title"}, "Open Library")

    def selected_factory(_api_key):
        provider = StubProvider()
        factories.append(provider)
        return provider

    selected = PROVIDER_REGISTRY[0]
    descriptors = (replace(selected, factory=selected_factory), *PROVIDER_REGISTRY[1:])
    monkeypatch.setattr("bookledger.ui.provider_diagnostic.threading.Thread", ImmediateThread)
    dialog._providers = tuple(descriptors)
    dialog._providers_by_name = {item.name: item for item in descriptors}
    dialog.provider_combo.configure(values=tuple(item.name for item in descriptors))
    dialog.provider_var.set(selected.name)
    dialog.isbn_var.set("9780553290998")

    dialog._start_test()
    dialog._poll_worker_results()

    assert calls == ["lookup"]
    assert len(factories) == 1
    assert factories[0].timeout == DIAGNOSTIC_TIMEOUT_SECONDS
    assert StubProvider.timeout == 2.5
    assert dialog.overall_status_var.get() == "Partial data"
    assert "Secret title" not in [var.get() for var in dialog._field_status_vars.values()]
    assert dialog._field_status_vars["Title"].get() == "OK"
    assert str(dialog.test_button.cget("state")) == "normal"
    assert re.fullmatch(r"\d+\.\d{2} seconds", dialog.fetch_time_var.get())


@pytest.mark.parametrize(
    ("failure_kind", "expected"),
    [("provider", "HTTP error"), ("unexpected", "Lookup error"), ("timeout", "Timeout")],
)
def test_provider_failures_leave_ui_recoverable(dialog, monkeypatch, failure_kind, expected):
    class FailingProvider:
        timeout = 5.0

        def lookup(self, _isbn):
            return MetadataResult("Lookup failed", {}, "Open Library", failure_kind=failure_kind)

    base = PROVIDER_REGISTRY[0]
    descriptor = replace(base, factory=lambda _key: FailingProvider())
    dialog._providers = (descriptor,)
    dialog._providers_by_name = {descriptor.name: descriptor}
    dialog.provider_combo.configure(values=(descriptor.name,))
    dialog.provider_var.set(descriptor.name)
    dialog.isbn_var.set("9780553290998")
    monkeypatch.setattr("bookledger.ui.provider_diagnostic.threading.Thread", ImmediateThread)

    dialog._start_test()
    dialog._poll_worker_results()

    assert dialog.overall_status_var.get() == expected
    assert str(dialog.test_button.cget("state")) == "normal"
    assert str(dialog.isbn_entry.cget("state")) == "normal"


def test_elapsed_time_threshold_and_display_format():
    assert elapsed_color(3.0) == TIME_FAST_COLOR
    assert elapsed_color(3.001) == TIME_SLOW_COLOR


def test_fetch_time_uses_two_decimals_and_applies_the_three_second_color_boundary(dialog, monkeypatch):
    monkeypatch.setattr("bookledger.ui.provider_diagnostic.threading.Thread", DeferredThread)
    dialog.isbn_var.set("9780553290998")
    dialog._start_test()
    descriptor = dialog._providers_by_name[dialog.provider_var.get()]
    result = MetadataResult("Retrieved", {field: "value" for field in descriptor.supported_fields})

    dialog._finish_result(dialog._operation_id, descriptor, result, 3.0)

    assert dialog.fetch_time_var.get() == "3.00 seconds"
    assert str(dialog.fetch_time_label.cget("foreground")) == TIME_FAST_COLOR

    dialog._start_test()
    dialog._finish_result(dialog._operation_id, descriptor, result, 3.001)
    assert dialog.fetch_time_var.get() == "3.00 seconds"
    assert str(dialog.fetch_time_label.cget("foreground")) == TIME_SLOW_COLOR


def test_diagnostic_timeout_setting_does_not_mutate_provider_class():
    assert DIAGNOSTIC_TIMEOUT_SECONDS == 5.0
    assert PROVIDER_REGISTRY[0].factory("").timeout == 5
