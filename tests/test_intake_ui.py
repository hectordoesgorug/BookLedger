import tkinter as tk

import pytest
from PIL import Image

from bookledger.config import APPROVED_GENRES, DEFAULT_LOCATION
from bookledger.db.database import Database
from bookledger.services.catalog import CatalogService
from bookledger.services.metadata import MetadataResult
from bookledger.services.photos import PhotoService
from bookledger.ui.forms import BookForm


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
def form(tmp_path, tk_root):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    db = Database(data_dir / "bookledger.sqlite3")
    service = CatalogService(db, data_dir)
    photo_service = PhotoService(data_dir / "photos")
    source_photo = tmp_path / "sample.png"
    Image.new("RGB", (100, 120), "white").save(source_photo)
    photo = photo_service.import_and_compress(source_photo)
    widget = BookForm(tk_root, service=service, photo_service=photo_service, on_saved=lambda: None)
    widget.update_idletasks()
    yield widget, tk_root, photo
    try:
        widget.destroy()
    except tk.TclError:
        pass


def test_add_form_layout_defaults_and_title_case_labels(form):
    widget, _root, _photo = form

    assert widget.title() == "Add Book"
    assert "actual_sale_price" not in widget._widgets
    assert "sale_date" not in widget._widgets
    assert widget._get("status") == "Available"
    assert widget._get("location") == DEFAULT_LOCATION
    assert tuple(widget._widgets["genre"]["values"]) == APPROVED_GENRES
    assert str(widget.refresh_button.cget("state")) == "disabled"
    assert [widget.save_button.cget("text"), widget.refresh_button.cget("text")] == ["Save Book", "Refresh"]
    assert [widget.clear_button.cget("text"), widget.cancel_button.cget("text")] == ["Clear", "Cancel"]
    assert widget.photo_panel.master is widget.right_panel
    assert widget.mobile_panel.master is widget.right_panel
    assert widget.actions_panel.master is widget.right_panel
    title_row = int(widget._widgets["title"].grid_info()["row"])
    title_error = widget._errors["title"].grid_info()
    assert int(title_error["row"]) > title_row
    assert int(title_error["column"]) == 1


def test_field_error_clears_when_value_becomes_valid(form):
    widget, _root, _photo = form
    widget._populate_validation({"title": "Title is required."})
    widget._set("title", "Entered Title")
    widget._clear_valid_error("title")
    assert widget._errors["title"].cget("text") == ""


def test_photo_preview_and_manual_metadata_values_are_preserved(form):
    widget, _root, photo = form
    widget._set("title", "Manually Entered Title")

    widget.set_photo(photo)
    widget._apply_metadata(MetadataResult("Retrieved", {"title": "Provider Title", "author": "Provider Author"}, "Open Library"))

    assert widget.photo_path.get() == str(photo)
    assert widget.photo_preview.cget("image")
    assert widget._get("title") == "Manually Entered Title"
    assert widget._get("author") == "Provider Author"


def test_connection_failure_refresh_retries_simulated_connection(form):
    widget, _root, _photo = form
    widget.connection_outcome.set("Connection Failed")
    widget._simulate_connection()
    operation_id = widget._active_operation[1]
    assert widget.mobile_status.get() == "Connecting to App…"
    widget._finish_connection(operation_id)
    assert widget.mobile_status.get() == "Connection Failed"
    assert str(widget.refresh_button.cget("state")) == "normal"

    widget.connection_outcome.set("Connected — Ready")
    widget._refresh()
    operation_id = widget._active_operation[1]
    widget._finish_connection(operation_id)
    assert widget.mobile_status.get() == "Connected — Ready"
    assert str(widget.refresh_button.cget("state")) == "disabled"


def test_scan_timeout_uses_ten_seconds_and_refresh_restarts_scan(form):
    widget, _root, _photo = form
    widget._connection_ready = True
    callbacks = {}
    widget.after = lambda delay, callback: callbacks.setdefault(delay, callback) or f"after-{delay}"
    widget.after_cancel = lambda _identifier: None

    widget._simulate_scan()
    assert widget.mobile_status.get() == "Scanning ISBN…"
    assert 10_000 in callbacks
    callbacks[10_000]()
    assert widget.mobile_status.get() == "Scan Failed"
    assert str(widget.refresh_button.cget("state")) == "normal"

    callbacks.clear()
    widget._refresh()
    assert widget.mobile_status.get() == "Scanning ISBN…"
    assert 10_000 in callbacks


def test_scan_success_and_future_photo_handoff_are_simulated(form):
    widget, _root, photo = form
    widget._connection_ready = True
    widget.mock_scan_isbn.set("9780306406157")
    callbacks = {}
    widget.after = lambda delay, callback: callbacks.setdefault(delay, callback) or f"after-{delay}"
    widget.after_cancel = lambda _identifier: None

    widget._simulate_scan()
    callbacks[200]()
    assert widget._get("isbn") == "9780306406157"
    assert widget.mobile_status.get() == "Connected — Ready"

    widget.phone_photo_capture_started()
    assert widget.mobile_status.get() == "Taking Photo…"
    widget.receive_photo(photo)
    assert widget.mobile_status.get() == "Photo Received"
    assert widget.photo_preview.cget("image")


def test_lookup_failure_is_refreshable_but_isbn_miss_is_not(form):
    widget, _root, _photo = form
    widget._set("isbn", "9780306406157")
    widget._set("title", "Keep My Manual Title")
    widget._active_operation = ("lookup", 44, "9780306406157")
    widget._finish_lookup(44, "9780306406157", MetadataResult("Lookup failed", {}, "Open Library", "timeout", "timeout"))
    assert widget.mobile_status.get() == "Lookup Failed — Request timed out."
    assert widget._get("title") == "Keep My Manual Title"
    assert str(widget.refresh_button.cget("state")) == "normal"

    retry_calls = []
    widget._lookup_metadata = lambda: retry_calls.append(widget._get("isbn"))
    widget._refresh()
    assert retry_calls == ["9780306406157"]

    widget._active_operation = ("lookup", 45, "9780306406157")
    widget._finish_lookup(45, "9780306406157", MetadataResult("No data", {}, "Google Books"))
    assert widget.mobile_status.get() == "ISBN Not Found"
    assert str(widget.refresh_button.cget("state")) == "disabled"


def test_edit_form_keeps_sale_details_but_add_form_does_not(form):
    widget, root, photo = form
    payload = {
        "title": "Example Book",
        "author": "Example Author",
        "isbn": "9780306406157",
        "genre": "Science",
        "format": "Paperback",
        "condition": "Good",
        "price": "500",
        "photo_path": str(photo),
    }
    copy_id = widget.service.create_copy(payload)
    row = widget.service.get_copy(copy_id)
    widget._close()

    edit_form = BookForm(root, service=widget.service, photo_service=widget.photo_service, on_saved=lambda: None, existing=row)
    edit_form.update_idletasks()
    assert "sale_date" in edit_form._widgets
    assert edit_form._field_labels["actual_sale_price"].cget("text") == "Price"
    assert edit_form._field_labels["sale_date"].cget("text") == "Date Sold"
    edit_form._close()


def test_clear_confirms_discard_and_cancel_closes_without_saving(form, monkeypatch):
    widget, _root, _photo = form
    widget._set("title", "Unsaved title")
    answers = iter((False, True))
    monkeypatch.setattr("bookledger.ui.forms.messagebox.askyesno", lambda *_args, **_kwargs: next(answers))

    widget._clear()
    assert widget._get("title") == "Unsaved title"
    widget._clear()
    assert widget._get("title") == ""
    assert widget._get("location") == DEFAULT_LOCATION
    assert widget._get("status") == "Available"
    assert widget.mobile_status.get() == "Idle — Ready"

    widget.cancel_button.invoke()
    assert not widget.winfo_exists()


def test_lookup_does_not_apply_stale_results_or_overlap_requests(form, monkeypatch):
    widget, root, _photo = form

    class DeferredThread:
        instances = []

        def __init__(self, *, target, **_kwargs):
            self.target = target
            self.instances.append(self)

        def start(self):
            pass

    monkeypatch.setattr("bookledger.ui.forms.threading.Thread", DeferredThread)
    widget._set("isbn", "9780306406157")
    widget._lookup_metadata()
    widget._lookup_metadata()
    operation_id = widget._active_operation[1]
    widget._set("isbn", "9780140449136")
    widget._set("title", "New Manual Title")
    assert len(DeferredThread.instances) == 1

    widget._finish_lookup(operation_id, "9780306406157", MetadataResult("Retrieved", {"title": "Old Provider Title"}, "Open Library"))

    assert widget._get("isbn") == "9780140449136"
    assert widget._get("title") == "New Manual Title"
