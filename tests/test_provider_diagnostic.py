from __future__ import annotations

import tkinter as tk
from dataclasses import replace
from pathlib import Path
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
    ttk_library = Path(str(root.tk.call("info", "library"))) / "ttk"
    if not (ttk_library / "sizegrip.tcl").is_file():
        root.destroy()
        pytest.skip("Tk UI tests require the complete Tcl/Tk library; ttk/sizegrip.tcl is missing")
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


def test_settings_tabs_relocate_controls_and_keep_future_integrations_nonfunctional(tk_root):
    class SettingsHarness:
        _build_settings = BookLedgerApp._build_settings
        _build_mobile_app_setup = BookLedgerApp._build_mobile_app_setup
        _build_metadata_sources = BookLedgerApp._build_metadata_sources
        _build_api_management = BookLedgerApp._build_api_management
        _build_storage_settings = BookLedgerApp._build_storage_settings
        _build_preferences = BookLedgerApp._build_preferences
        _build_poster_setup = BookLedgerApp._build_poster_setup
        _build_value_list_editor = BookLedgerApp._build_value_list_editor
        _show_hover_tooltip = BookLedgerApp._show_hover_tooltip
        _hide_hover_tooltip = BookLedgerApp._hide_hover_tooltip
        _provider_drag_start = BookLedgerApp._provider_drag_start
        _provider_drag_motion = BookLedgerApp._provider_drag_motion
        _provider_drag_end = BookLedgerApp._provider_drag_end
        _reorder_provider_rows = BookLedgerApp._reorder_provider_rows
        _load_google_books_key = BookLedgerApp._load_google_books_key

    harness = SettingsHarness()
    harness.workspace = ttk.Frame(tk_root)
    harness.workspace.pack(fill="both", expand=True)
    harness.paths = SimpleNamespace(
        root=Path("portable-data"), google_books_config=Path("portable-data/assets/google_books.json")
    )
    harness.config_store = SimpleNamespace(get=lambda *_args: "")
    harness._available_theme_names = ("clam", "flatly")
    harness._active_theme = "clam"
    harness._apply_theme_selection = lambda: None
    harness.lifecycle = SimpleNamespace(trash_count=lambda: 1)
    harness.catalog = SimpleNamespace(
        list_genres=lambda: ("Science", "Fiction"),
        list_formats=lambda: ("Paperback", "Hardcover"),
        list_locations=lambda: ("Shelf", "Storage"),
        value_assignment_count=lambda kind, value: int(kind == "genre" and value == "Science"),
        location_assignment_count=lambda _value: 0,
        add_genre=lambda value: value,
        rename_genre=lambda old, new: new,
        delete_genre=lambda _value: None,
        add_format=lambda value: value,
        rename_format=lambda old, new: new,
        delete_format=lambda _value: None,
        add_location=lambda value: value,
        rename_location=lambda old, new: new,
        delete_location=lambda _value: None,
    )
    harness.provider_settings = SimpleNamespace(
        enabled={descriptor.id: True for descriptor in PROVIDER_REGISTRY},
        order=[descriptor.id for descriptor in PROVIDER_REGISTRY],
    )
    harness.provider_settings_store = SimpleNamespace(warning=None, active_path="config.json")
    actions = []
    for name in (
        "create_backup", "verify_database", "restore_backup", "restore_latest", "clear_trash",
        "purge_data", "retry_storage_recovery", "export_inventory_csv", "view_log", "clear_log",
        "_toggle_logging", "_save_provider_settings", "_restore_provider_defaults",
        "_save_google_books_key", "_remove_google_books_key", "_test_google_books_lookup",
    ):
        setattr(harness, name, lambda action=name: actions.append(action))
    harness._show_api_help = lambda provider: actions.append(("help", provider))
    harness._logging_enabled = False
    harness._logging_warning = ""
    harness._configuration_warnings = ()
    harness._load_google_books_key = lambda: ""

    harness._build_settings()
    tk_root.geometry("1280x800")
    tk_root.deiconify()
    tk_root.update()
    notebook = harness.settings_notebook
    assert notebook.winfo_width() >= 1000
    assert notebook.winfo_height() >= 600
    expected_tabs = (
        "Mobile App Setup", "Metadata Sources", "API Management", "Storage and Backup", "Poster Setup", "Preferences",
    )
    assert tuple(notebook.tab(index, "text") for index in range(len(expected_tabs))) == expected_tabs
    assert {descriptor.name for descriptor in PROVIDER_REGISTRY} == {
        "Open Library", "Google Books", "Booktopia",
    }

    def tab_widgets(index):
        return tuple(_walk_widgets(notebook.nametowidget(notebook.tabs()[index])))

    def texts(index):
        return tuple(str(widget.cget("text")) for widget in tab_widgets(index) if "text" in widget.keys())

    mobile_text = " ".join(texts(0))
    assert "reserved for future development" in mobile_text
    assert not [widget for widget in tab_widgets(0) if isinstance(widget, ttk.Button)]
    metadata_text = " ".join(texts(1))
    for name in ("Open Library", "Google Books", "Booktopia", "ISBNdb", "WorldCat", "Internet Archive", "BigBook", "Hardcover", "Goodreads", "ISBN Lookup Test"):
        assert name in metadata_text
    api_text = " ".join(texts(2))
    for name in ("Google Books API key", "ISBNdb", "BigBook", "Hardcover", "unavailable until integrated"):
        assert name in api_text
    storage_text = " ".join(texts(3))
    for name in ("Back Up Now", "Export to CSV…", "Verify Database", "Restore Backup…", "Undo Delete", "Clear Trash…", "Purge Data…", "Retry Recovery", "View Log", "Clear Log…", "Enable Logging"):
        assert name in storage_text
    assert "Data folder:" not in storage_text and "Database:" not in storage_text and "Open Data Folder" not in storage_text
    assert "Google Books API key" not in storage_text
    poster_text = " ".join(texts(4))
    assert "reserved for future development" in poster_text
    preferences_text = " ".join(texts(5))
    assert all(name in preferences_text for name in ("Genre", "Format", "Location", "Theme:", "Apply"))
    assert "Preview" not in preferences_text
    assert "not available yet" not in preferences_text
    assert "Manage Locations" not in preferences_text
    preference_widgets = tab_widgets(5)
    science_row = next(
        widget for widget in preference_widgets
        if isinstance(widget, ttk.Label) and widget.cget("text") == "Science"
    ).master
    delete_button = next(
        widget for widget in science_row.winfo_children()
        if isinstance(widget, ttk.Button) and widget.cget("text") == "Delete"
    )
    assert delete_button.instate(("disabled",))
    assert delete_button.bind("<Enter>")
    assert not any(
        isinstance(widget, ttk.Label) and widget.cget("text") == "ⓘ"
        for widget in science_row.winfo_children()
    )
    theme_selector = next(widget for widget in preference_widgets if isinstance(widget, ttk.Combobox))
    assert str(theme_selector.cget("state")) == "readonly"
    assert tuple(theme_selector.cget("values")) == harness._available_theme_names

    # Merely changing tabs does not invoke any Settings operation.
    for index in range(len(expected_tabs)):
        notebook.select(index)
        tk_root.update_idletasks()
    assert actions == []

    buttons_by_tab = tuple(
        [widget for widget in tab_widgets(index) if isinstance(widget, ttk.Button)]
        for index in range(len(expected_tabs))
    )
    metadata_buttons = [button.cget("text") for button in buttons_by_tab[1]]
    assert metadata_buttons == ["Save Metadata Sources", "Restore Defaults", "Test", "Clear"]
    api_buttons = [button.cget("text") for button in buttons_by_tab[2]]
    assert api_buttons == ["Show", "Test Lookup", "Save", "Remove", "?", "?", "?", "?"]
    assert buttons_by_tab[0] == []
    assert buttons_by_tab[3][0].cget("text") == "Back Up Now"
    assert buttons_by_tab[3][0].cget("style") == ""
    assert buttons_by_tab[4] == []
    assert next(button for button in buttons_by_tab[3] if button.cget("text") == "View Log").instate(("disabled",))
    assert next(button for button in buttons_by_tab[3] if button.cget("text") == "Clear Log…").instate(("disabled",))

    def invoke(tab_index, label):
        button = next(widget for widget in buttons_by_tab[tab_index] if widget.cget("text") == label)
        button.invoke()

    invoke(1, "Save Metadata Sources")
    invoke(1, "Restore Defaults")
    invoke(2, "Save")
    invoke(2, "Remove")
    invoke(2, "Test Lookup")
    invoke(2, "?")
    invoke(3, "Back Up Now")
    invoke(3, "Export to CSV…")
    invoke(3, "Verify Database")
    invoke(3, "Restore Backup…")
    invoke(3, "Undo Delete")
    invoke(3, "Clear Trash…")
    invoke(3, "Purge Data…")
    invoke(3, "Retry Recovery")
    invoke(3, "View Log")
    invoke(3, "Clear Log…")
    assert [action for action in actions if isinstance(action, str)] == [
        "_save_provider_settings", "_restore_provider_defaults", "_save_google_books_key",
        "_remove_google_books_key", "_test_google_books_lookup", "create_backup", "export_inventory_csv",
        "verify_database", "restore_backup", "restore_latest", "clear_trash", "purge_data",
        "retry_storage_recovery",
    ]
    assert ("help", "Google Books") in actions


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


def test_google_books_test_lookup_does_not_save_the_draft_key(monkeypatch):
    calls = []
    result = SimpleNamespace(status="No data", failure_kind=None, error="must not surface")

    class Provider:
        def __init__(self, api_key):
            calls.append(("provider", api_key))

        def lookup(self, isbn):
            calls.append(("lookup", isbn))
            return result

    monkeypatch.setattr(app_module, "GoogleBooksProvider", Provider)
    monkeypatch.setattr(app_module.threading, "Thread", ImmediateThread)
    subject = SimpleNamespace(
        google_books_key_var=SimpleNamespace(get=lambda: "draft-key"),
        google_books_api_status=SimpleNamespace(set=lambda value: calls.append(("status", value))),
        _save_google_books_key=lambda: (_ for _ in ()).throw(AssertionError("test must not save credentials")),
        winfo_exists=lambda: True,
        after=lambda _delay, callback: callback(),
    )

    BookLedgerApp._test_google_books_lookup(subject)

    assert ("provider", "draft-key") in calls
    assert ("lookup", "9780306406157") in calls
    assert any("metadata lookup succeeded" in value for kind, value in calls if kind == "status")
    assert all("must not surface" not in value for kind, value in calls if kind == "status")


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
    assert FIELD_COLORS["N/A"] == FIELD_COLORS["No Data"]


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
