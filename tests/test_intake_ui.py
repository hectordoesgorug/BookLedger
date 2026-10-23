import tkinter as tk
from types import SimpleNamespace

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
    assert "status" not in widget._widgets
    assert widget._get("location") == DEFAULT_LOCATION
    assert widget.open_library_status.get() == "Not attempted"
    assert widget.google_books_status.get() == "Not attempted"
    assert widget.booktopia_status.get() == "Not attempted"
    assert tuple(widget._widgets["genre"]["values"]) == APPROVED_GENRES
    assert str(widget.refresh_button.cget("state")) == "disabled"
    assert [widget.save_button.cget("text"), widget.refresh_button.cget("text")] == ["Save Book", "Refresh"]
    assert [widget.clear_button.cget("text"), widget.cancel_button.cget("text")] == ["Clear", "Cancel"]
    assert widget.photo_panel.master is widget.right_panel
    assert widget.mobile_panel.master is widget.right_panel
    assert widget.actions_panel.master is widget.right_panel
    title_row = int(widget._widgets["title"].grid_info()["row"])
    assert int(widget._field_labels["title"].grid_info()["row"]) == title_row
    title_error = widget._errors["title"].grid_info()
    assert int(title_error["row"]) == title_row + 1
    assert int(title_error["column"]) == 1
    assert widget._field_labels["srp"].cget("text") == "SRP"


def test_short_fields_use_the_approved_two_column_form_layout(form):
    widget, _root, _photo = form
    for left_key, right_key in (
        ("genre", "edition"),
        ("publisher", "page_count"),
        ("publication_year", "srp"),
        ("format", "location"),
        ("condition", "price"),
    ):
        left = widget._widgets[left_key].grid_info()
        right = widget._widgets[right_key].grid_info()
        assert left["row"] == right["row"]
        assert widget._widgets[left_key].master is widget.body
        assert widget._widgets[right_key].master is widget.body
        assert int(widget._field_labels[left_key].grid_info()["column"]) == 0
        assert int(left["column"]) == 1
        assert int(widget._field_labels[right_key].grid_info()["column"]) == 2
        assert int(right["column"]) == 3
        assert int(widget._field_labels[left_key].grid_info()["row"]) == int(left["row"])
        assert int(widget._field_labels[right_key].grid_info()["row"]) == int(right["row"])
        for key in (left_key, right_key):
            field = widget._widgets[key].grid_info()
            error = widget._errors[key].grid_info()
            assert widget._errors[key].master is widget.body
            assert int(error["row"]) == int(field["row"]) + 1
            assert int(error["column"]) == int(field["column"])

    widget.update_idletasks()
    left_input = widget._widgets["genre"]
    right_label = widget._field_labels["edition"]
    assert right_label.winfo_x() - (left_input.winfo_x() + left_input.winfo_width()) >= 16

    for key in ("title", "author", "isbn"):
        field = widget._widgets[key].grid_info()
        label = widget._field_labels[key].grid_info()
        error = widget._errors[key].grid_info()
        assert int(label["row"]) == int(field["row"])
        assert int(field["column"]) == 1
        assert int(field["columnspan"]) == 3
        assert int(error["row"]) == int(field["row"]) + 1
    synopsis = widget._widgets["book_details"].grid_info()
    assert int(synopsis["column"]) == 1
    assert int(synopsis["columnspan"]) == 3
    assert int(widget._field_labels["book_details"].grid_info()["row"]) == int(synopsis["row"])
    photo_controls = widget.photo_path_label.master.grid_info()
    assert int(photo_controls["columnspan"]) == 3
    assert int(photo_controls["row"]) == int(widget._field_labels["photo_path"].grid_info()["row"])
    assert int(widget._errors["photo_path"].grid_info()["row"]) == int(photo_controls["row"]) + 1


def test_form_minimum_size_keeps_scrollable_content_reachable(form):
    widget, root, _photo = form
    root.deiconify()
    root.geometry("400x300+0+0")
    widget.geometry("960x700")
    widget.update()
    canvas = widget.body.master
    canvas.update_idletasks()
    body_height = widget.body.winfo_reqheight()
    viewport_height = canvas.winfo_height()
    assert body_height > 0
    assert viewport_height > 0
    scroll_region = tuple(map(int, canvas.cget("scrollregion").split()))
    assert scroll_region[3] >= body_height
    assert body_height > viewport_height
    assert widget.body.winfo_width() <= canvas.winfo_width()
    short_keys = ("genre", "edition", "publisher", "page_count", "publication_year", "srp", "format", "location", "condition", "price")
    input_widths = {widget._widgets[key].winfo_width() for key in short_keys}
    assert len(input_widths) == 1
    short_row = int(widget._widgets["genre"].grid_info()["row"])
    assert widget.body.grid_bbox(0, short_row, 1, 1)[2] == widget.body.grid_bbox(2, short_row, 1, 1)[2]
    for key in short_keys:
        error = widget._errors[key]
        assert int(error.cget("wraplength")) == error.winfo_width()
    # Scrolling remains available at the minimum supported window size.
    assert int(widget.minsize()[1]) == 700

    for geometry in ("1120x850", "1400x900"):
        widget.geometry(geometry)
        widget.update()
        short_row = int(widget._widgets["genre"].grid_info()["row"])
        assert widget.body.grid_bbox(0, short_row, 1, 1)[2] == widget.body.grid_bbox(2, short_row, 1, 1)[2]
        assert len({widget._widgets[key].winfo_width() for key in short_keys}) == 1
        assert all(widget._errors[key].winfo_width() == widget._widgets[key].winfo_width() for key in short_keys)


def test_edit_form_uses_the_same_two_column_layout(form):
    widget, root, photo = form
    edit = BookForm(
        root,
        service=widget.service,
        photo_service=widget.photo_service,
        on_saved=lambda: None,
        existing={
            "title": "An Existing Book", "author": "Test Author", "genre": "Science",
            "format": "Paperback", "condition": "Good", "location": "Shelf",
            "price_minor": 50000, "status": "Available", "srp_minor": None,
        },
    )
    edit.update_idletasks()
    assert int(edit._field_labels["genre"].grid_info()["row"]) == int(edit._widgets["genre"].grid_info()["row"])
    assert int(edit._widgets["genre"].grid_info()["column"]) == 1
    assert int(edit._widgets["edition"].grid_info()["column"]) == 3
    assert int(edit._errors["genre"].grid_info()["row"]) == int(edit._widgets["genre"].grid_info()["row"]) + 1
    assert int(edit.photo_path_label.master.grid_info()["columnspan"]) == 3
    assert edit._field_labels["srp"].cget("text") == "SRP"
    edit.destroy()


def test_lookup_keeps_all_provider_statuses_not_attempted_until_service_reports_progress(form, monkeypatch):
    widget, _root, _photo = form

    class DeferredThread:
        def __init__(self, *, target, **_kwargs):
            self.target = target

        def start(self):
            pass

    monkeypatch.setattr("bookledger.ui.forms.threading.Thread", DeferredThread)
    widget._set("isbn", "9780306406157")

    widget._lookup_metadata()

    assert widget.open_library_status.get() == "Not attempted"
    assert widget.google_books_status.get() == "Not attempted"
    assert widget.booktopia_status.get() == "Not attempted"


def test_field_error_clears_when_value_becomes_valid(form):
    widget, _root, _photo = form
    widget._populate_validation({"title": "Title is required."})
    widget._set("title", "Entered Title")
    widget._clear_valid_error("title")
    assert widget._errors["title"].cget("text") == ""


def test_missing_optional_metadata_displays_no_data_and_saves_as_null(form):
    widget, _root, photo = form
    optional = ("publisher", "publication_year", "edition", "page_count", "srp", "book_details")
    for key in optional:
        field = widget._widgets[key]
        displayed = field.get("1.0", "end-1c").strip() if isinstance(field, tk.Text) else field.get().strip()
        assert displayed == "No Data"
        assert widget._get(key) == ""

    widget._set("title", "Minimal Book")
    widget._set("author", "Test Author")
    widget._set("genre", "Science")
    widget._set("format", "Paperback")
    widget._set("condition", "Good")
    widget._set("price", "500")
    widget.set_photo(photo)
    copy_id = widget.service.create_copy(widget._payload())

    with widget.service.db.connect() as conn:
        row = conn.execute(
            "SELECT publisher,publication_year,edition,page_count,srp_minor,book_details FROM book_records WHERE id=(SELECT book_id FROM copies WHERE id=?)",
            (copy_id,),
        ).fetchone()
    assert tuple(row) == (None, None, None, None, None, None)


def test_srp_is_readonly_but_provider_values_can_be_saved(form):
    widget, _root, photo = form
    srp_field = widget._widgets["srp"]
    assert str(srp_field.cget("state")) == "readonly"

    widget._apply_metadata(MetadataResult("Retrieved", {"srp": "825.25"}, "Google Books"))
    srp_field.insert(0, "999.00")
    assert widget._get("srp") == "825.25"
    widget._set("title", "Reference Price Book")
    widget._set("author", "Test Author")
    widget._set("genre", "Science")
    widget._set("format", "Paperback")
    widget._set("condition", "Good")
    widget._set("price", "500")
    widget.set_photo(photo)
    copy_id = widget.service.create_copy(widget._payload())

    with widget.service.db.connect() as conn:
        srp_minor = conn.execute(
            "SELECT b.srp_minor FROM book_records b JOIN copies c ON c.book_id=b.id WHERE c.id=?",
            (copy_id,),
        ).fetchone()[0]
    assert srp_minor == 82525


def test_optional_metadata_placeholder_can_be_replaced_with_manual_value(form):
    widget, _root, _photo = form
    widget._clear_placeholder("publisher")
    widget._widgets["publisher"].insert(0, "Manual Press")
    widget._restore_placeholder("publisher")

    assert widget._get("publisher") == "Manual Press"
    assert widget._payload()["publisher"] == "Manual Press"


def test_photo_preview_and_manual_metadata_values_are_preserved(form):
    widget, _root, photo = form
    widget._set("title", "Manually Entered Title")
    widget._set("author", "Manually Entered Author")
    widget._set("format", "Hardcover")

    widget.set_photo(photo)
    widget._apply_metadata(MetadataResult(
        "Retrieved", {"title": "Provider Title", "author": "Provider Author", "format": "Paperback"}, "Open Library"
    ))

    assert widget.photo_path.get() == str(photo)
    assert widget.photo_preview.cget("image")
    assert widget._get("title") == "Manually Entered Title"
    assert widget._get("author") == "Manually Entered Author"
    assert widget._get("format") == "Hardcover"

    widget._set("format", "")
    widget._apply_metadata(MetadataResult("Retrieved", {"format": "Paperback"}, "Booktopia"))
    assert widget._get("format") == "Paperback"


def test_booktopia_title_and_author_populate_empty_add_form_fields(form):
    widget, _root, _photo = form
    widget._set("isbn", "9780553290998")
    widget._active_operation = ("lookup", 49, "9780553290998")

    widget._finish_lookup(49, "9780553290998", MetadataResult("Retrieved", {
        "title": "Nightfall", "author": "Isaac Asimov", "publication_year": 1991,
        "book_details": "Synthetic synopsis.",
    }, "Booktopia", provider_statuses={"Booktopia": "Metadata retrieved"}))

    assert widget._get("title") == "Nightfall"
    assert widget._get("author") == "Isaac Asimov"
    assert widget._get("publication_year") == "1991"
    assert widget._get("book_details") == "Synthetic synopsis."


def test_add_form_metadata_mapping_populates_title_and_author_without_tk_root():
    class Entry:
        def __init__(self, value=""):
            self.value = value
            self.state = "normal"

        def get(self):
            return self.value

        def cget(self, key):
            assert key == "state"
            return self.state

        def configure(self, *, state):
            self.state = state

        def delete(self, *_args):
            self.value = ""

        def insert(self, _index, value):
            self.value = str(value)

    class Status:
        def set(self, _value):
            pass

    fields = (
        "title", "author", "genre", "book_details", "publisher", "publication_year",
        "edition", "page_count", "format", "srp",
    )
    form = SimpleNamespace(
        _widgets={key: Entry("Manual Title") if key == "title" else Entry() for key in fields},
        metadata_status=Status(),
    )
    form._get = lambda key: BookForm._get(form, key)
    form._set = lambda key, value: BookForm._set(form, key, value)

    BookForm._apply_metadata(form, MetadataResult("Retrieved", {
        "title": "Provider Title", "author": "Isaac Asimov",
    }, "Booktopia"))

    assert form._get("title") == "Manual Title"
    assert form._get("author") == "Isaac Asimov"


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
    assert widget.metadata_status.get().startswith("Metadata unavailable")
    assert widget.mobile_status.get() == "Idle — Ready"
    assert widget._get("title") == "Keep My Manual Title"
    assert str(widget.refresh_button.cget("state")) == "normal"

    retry_calls = []
    widget._lookup_metadata = lambda: retry_calls.append(widget._get("isbn"))
    widget._refresh()
    assert retry_calls == ["9780306406157"]

    widget._active_operation = ("lookup", 45, "9780306406157")
    widget._finish_lookup(45, "9780306406157", MetadataResult("No data", {}, "Google Books", record_found=False))
    assert widget.metadata_status.get().startswith("No matching ISBN record")
    assert str(widget.refresh_button.cget("state")) == "disabled"


def test_unverified_provider_results_do_not_appear_as_a_confirmed_isbn_miss(form):
    widget, _root, _photo = form
    isbn = "9780385504201"
    widget._set("isbn", isbn)
    widget._active_operation = ("lookup", 47, isbn)
    widget._finish_lookup(47, isbn, MetadataResult(
        "No data", {}, "Google Books", "internal details", "unverified",
        record_found=False,
        provider_statuses={
            "Open Library": "No matching record",
            "Google Books": "Results returned · ISBN not confirmed",
        },
    ))

    assert widget.google_books_status.get() == "Results returned · ISBN not confirmed"
    assert widget.metadata_status.get() == "Results returned, but ISBN could not be confirmed · Google Books"


def test_successful_fallback_lookup_reports_primary_provider_failure(form):
    widget, _root, _photo = form
    isbn = "9780306406157"
    widget._set("isbn", isbn)
    widget._active_operation = ("lookup", 46, isbn)

    widget._set("title", "My Manual Title")
    widget._finish_lookup(46, isbn, MetadataResult(
        "Retrieved", {"title": "Fallback Title", "publisher": "Fallback Press"}, "Google Books",
        "timed out", "timeout",
        provider_statuses={
            "Open Library": "Timed out",
            "Google Books": "Metadata retrieved · some fields missing",
            "Booktopia": "Metadata retrieved",
        },
        partial=True,
    ))

    assert widget._get("title") == "My Manual Title"
    assert widget._get("publisher") == "Fallback Press"
    assert widget.metadata_status.get().startswith("Partially retrieved")
    assert widget.open_library_status.get() == "Timed out"
    assert widget.google_books_status.get() == "Metadata retrieved · some fields missing"
    assert widget.booktopia_status.get() == "Metadata retrieved"


def test_partial_lookup_without_description_reports_book_details_unavailable(form):
    widget, _root, _photo = form
    isbn = "9780306406157"
    widget._set("isbn", isbn)
    widget._active_operation = ("lookup", 48, isbn)

    widget._finish_lookup(48, isbn, MetadataResult(
        "Retrieved", {"title": "Example Book", "author": "Example Author"}, "Open Library + Google Books",
        record_found=True,
        provider_statuses={
            "Open Library": "Metadata retrieved · some fields missing",
            "Google Books": "Metadata retrieved · some fields missing",
        },
        partial=True,
    ))

    assert widget._get("title") == "Example Book"
    assert widget.metadata_status.get() == (
        "Partially retrieved · Open Library + Google Books · Book Details unavailable"
    )


def test_edit_form_uses_one_contextual_price_and_keeps_status_out_of_form(form):
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
    assert "sale_date" not in edit_form._widgets
    assert "actual_sale_price" not in edit_form._widgets
    assert "status" not in edit_form._widgets
    assert "price" in edit_form._widgets
    edit_form._close()


def test_sold_copy_price_is_locked_in_edit_form(form):
    widget, root, photo = form
    payload = {
        "title": "Sold Book", "author": "Example Author", "isbn": "9780306406157",
        "genre": "Science", "format": "Paperback", "condition": "Good",
        "price": "500", "photo_path": str(photo),
    }
    copy_id = widget.service.create_copy(payload)
    widget.service.change_status(copy_id, "Sold")
    row = widget.service.get_copy(copy_id)
    widget._close()
    edit_form = BookForm(root, service=widget.service, photo_service=widget.photo_service, on_saved=lambda: None, existing=row)
    edit_form.update_idletasks()
    assert str(edit_form._widgets["price"].cget("state")) == "disabled"
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
    assert "status" not in widget._widgets
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


def test_clear_cancels_lookup_callbacks_and_allows_a_new_lookup(form, monkeypatch):
    widget, _root, _photo = form

    class DeferredThread:
        instances = []

        def __init__(self, *, target, **_kwargs):
            self.target = target
            self.instances.append(self)

        def start(self):
            pass

    monkeypatch.setattr("bookledger.ui.forms.threading.Thread", DeferredThread)
    monkeypatch.setattr("bookledger.ui.forms.messagebox.askyesno", lambda *_args, **_kwargs: True)
    widget._set("isbn", "9780306406157")
    widget._lookup_metadata()
    old_id = widget._active_operation[1]

    widget._clear()
    assert widget._active_operation is None
    assert widget.open_library_status.get() == "Not attempted"
    widget._set("isbn", "9780140449136")
    widget._lookup_metadata()
    new_id = widget._active_operation[1]
    widget._finish_lookup(old_id, "9780306406157", MetadataResult("Retrieved", {"title": "Old"}, "Open Library"))

    assert new_id != old_id
    assert widget._get("title") == ""
    assert widget.metadata_status.get() == "Looking up ISBN…"
