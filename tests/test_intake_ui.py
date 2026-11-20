import tkinter as tk
from types import SimpleNamespace
from tkinter import ttk

import pytest
from PIL import Image
from ttkbootstrap import Style

from bookledger.config import APPROVED_GENRES, DEFAULT_LOCATION
from bookledger.db.database import Database
from bookledger.provider_registry import PROVIDERS_BY_NAME
from bookledger.services.catalog import CatalogService
from bookledger.services.metadata import MetadataLookupService, MetadataResult
from bookledger.services.photos import PhotoService
from bookledger.ui.forms import BookForm


@pytest.fixture
def tk_root():
    try:
        root = tk.Tk()
        Style(theme="clam")
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


def test_metadata_keeps_provider_full_title_and_never_splits_or_overwrites_subtitle():
    class Value:
        def __init__(self, value=""):
            self.value = value

        def get(self):
            return self.value

        def set(self, value):
            self.value = value

    values = {key: "" for key in (
        "title", "subtitle", "author", "genre", "book_details", "publisher",
        "publication_year", "edition", "page_count", "format", "srp",
    )}
    subject = SimpleNamespace(
        metadata_source=None,
        metadata_status=Value(),
        _widgets={key: object() for key in values},
        _get=lambda key: values.get(key, ""),
        _set=lambda key, value: values.__setitem__(key, value or ""),
        _update_description_controls=lambda: None,
    )

    BookForm._apply_metadata(subject, MetadataResult(
        "Retrieved", {"title": "Provider Full Title: Provider Subtitle"}, "Open Library"
    ))
    assert values["title"] == "Provider Full Title: Provider Subtitle"
    assert values["subtitle"] == ""

    values.update(title="Manual title", subtitle="Manual subtitle")
    BookForm._apply_metadata(subject, MetadataResult(
        "Retrieved", {"title": "Replacement provider title"}, "Open Library"
    ))
    assert values["title"] == "Manual title"
    assert values["subtitle"] == "Manual subtitle"


def test_add_form_layout_defaults_and_title_case_labels(form):
    widget, _root, _photo = form

    assert widget.title() == "Add Book"
    assert "actual_sale_price" not in widget._widgets
    assert "sale_date" not in widget._widgets
    assert "status" not in widget._widgets
    assert widget._get("location") == DEFAULT_LOCATION
    assert list(widget.provider_status_vars) == ["Open Library", "Google Books", "Archive.org", "Booktopia"]
    assert all(status.get() == "Not attempted" for status in widget.provider_status_vars.values())
    provider_labels = [
        child.cget("text") for child in widget.metadata_status_panel.winfo_children()
        if isinstance(child, ttk.Label) and child.cget("text").endswith(":")
    ]
    assert provider_labels == ["Open Library:", "Google Books:", "Archive.org:", "Booktopia:"]
    assert not any(
        child.cget("text") == "Fields marked * are required. Metadata lookup is optional."
        for child in widget.body.winfo_children()
        if isinstance(child, ttk.Label)
    )
    assert widget.error_summary.master is widget.body
    assert tuple(widget._widgets["genre"]["values"]) == APPROVED_GENRES
    assert str(widget.refresh_button.cget("state")) == "disabled"
    assert [widget.save_button.cget("text"), widget.refresh_button.cget("text")] == ["Save Book", "Refresh"]
    assert [widget.clear_button.cget("text"), widget.cancel_button.cget("text")] == ["Clear", "Cancel"]
    assert widget.photo_panel.master is widget.right_panel
    assert widget.metadata_status_panel.master is widget.right_panel
    assert widget.actions_panel.master is widget.body
    assert widget.actions_panel.grid_info()["columnspan"] == 4
    assert [widget.actions_panel.grid_slaves(row=0, column=column)[0].cget("text") for column in range(4)] == [
        "Save Book", "Refresh", "Clear", "Cancel",
    ]
    assert not hasattr(widget, "_simulate_connection")
    assert not hasattr(widget, "_simulate_scan")
    assert not hasattr(widget, "mobile_panel")
    title_row = int(widget._widgets["title"].grid_info()["row"])
    assert int(widget._widgets["subtitle"].grid_info()["row"]) == title_row + 2
    assert widget._get("subtitle") == ""
    assert int(widget._field_labels["title"].grid_info()["row"]) == title_row
    title_error = widget._errors["title"].grid_info()
    assert int(title_error["row"]) == title_row + 1
    assert int(title_error["column"]) == 1
    assert widget._field_labels["srp"].cget("text") == "SRP (PHP)"


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
    assert int(widget._field_labels["book_details"].grid_info()["row"]) + 1 == int(synopsis["row"])
    photo_controls = widget.photo_path_label.master.grid_info()
    assert int(photo_controls["columnspan"]) == 3
    assert int(photo_controls["row"]) == int(widget._field_labels["photo_path"].grid_info()["row"])
    assert int(widget._errors["photo_path"].grid_info()["row"]) == int(photo_controls["row"]) + 1


def test_form_minimum_size_keeps_scrollable_content_reachable(form):
    widget, root, _photo = form
    root.deiconify()
    widget.deiconify()
    root.update()
    default_size = (widget.winfo_width(), widget.winfo_height())
    expected_height = max(700, max(widget.body.winfo_reqheight(), widget.right_panel.winfo_reqheight()) + 28)
    assert default_size == (1120, expected_height)
    assert default_size[1] < 850
    assert widget.right_panel.grid_rowconfigure(0)["weight"] == 1
    assert widget.photo_preview.cget("text") == "No Photo Selected"
    assert widget.photo_preview.cget("anchor") == "center"
    default_preview_height = widget.photo_panel.winfo_height()
    assert widget.metadata_status_panel.winfo_y() + widget.metadata_status_panel.winfo_height() <= widget.right_panel.winfo_height()

    root.geometry("400x300+0+0")
    widget.geometry("960x700")
    root.update()
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
    assert max(input_widths) - min(input_widths) <= 1
    short_row = int(widget._widgets["genre"].grid_info()["row"])
    assert widget.body.grid_bbox(0, short_row, 1, 1)[2] == widget.body.grid_bbox(2, short_row, 1, 1)[2]
    for key in short_keys:
        error = widget._errors[key]
        assert int(error.cget("wraplength")) == error.winfo_width()
    # Scrolling remains available at the minimum supported window size.
    assert int(widget.minsize()[1]) == 700
    minimum_preview_height = widget.photo_panel.winfo_height()
    assert minimum_preview_height < default_preview_height
    assert widget.photo_panel.winfo_ismapped()
    assert widget.metadata_status_panel.winfo_ismapped()
    assert widget.metadata_status_panel.winfo_y() + widget.metadata_status_panel.winfo_height() <= widget.right_panel.winfo_height()
    assert all(button.winfo_ismapped() for button in (widget.save_button, widget.refresh_button, widget.clear_button, widget.cancel_button))
    canvas.yview_moveto(1.0)
    root.update()
    assert canvas.canvasy(0) > 0
    assert widget.actions_panel.winfo_rooty() + widget.actions_panel.winfo_height() <= canvas.winfo_rooty() + canvas.winfo_height()

    preview_heights = [minimum_preview_height]
    for geometry in ("1120x850", "1400x900"):
        widget.geometry(geometry)
        root.update()
        short_row = int(widget._widgets["genre"].grid_info()["row"])
        assert widget.body.grid_bbox(0, short_row, 1, 1)[2] == widget.body.grid_bbox(2, short_row, 1, 1)[2]
        input_widths = {widget._widgets[key].winfo_width() for key in short_keys}
        assert max(input_widths) - min(input_widths) <= 1
        assert all(widget._errors[key].winfo_width() == widget._widgets[key].winfo_width() for key in short_keys)
        preview_heights.append(widget.photo_panel.winfo_height())
        assert widget.photo_panel.winfo_ismapped()
        assert widget.photo_preview.winfo_ismapped()
        assert widget.metadata_status_panel.winfo_ismapped()
        assert widget.metadata_status_panel.winfo_y() >= widget.photo_panel.winfo_y() + widget.photo_panel.winfo_height()
        assert widget.metadata_status_panel.winfo_y() + widget.metadata_status_panel.winfo_height() <= widget.right_panel.winfo_height()
        assert all(button.winfo_ismapped() for button in (widget.save_button, widget.refresh_button, widget.clear_button, widget.cancel_button))

    assert preview_heights[0] < default_preview_height < preview_heights[1] < preview_heights[2]


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
            "photo_path": str(photo),
        },
    )
    root.deiconify()
    edit.deiconify()
    root.update()
    assert int(edit._field_labels["genre"].grid_info()["row"]) == int(edit._widgets["genre"].grid_info()["row"])
    assert int(edit._widgets["genre"].grid_info()["column"]) == 1
    assert int(edit._widgets["edition"].grid_info()["column"]) == 3
    assert int(edit._errors["genre"].grid_info()["row"]) == int(edit._widgets["genre"].grid_info()["row"]) + 1
    assert int(edit.photo_path_label.master.grid_info()["columnspan"]) == 3
    assert edit.actions_panel.master is edit.body
    assert edit.photo_panel.master is edit.right_panel
    assert edit.metadata_status_panel.master is edit.right_panel
    assert edit.right_panel.grid_rowconfigure(0)["weight"] == 1
    assert edit.photo_preview.cget("image")
    assert edit.metadata_status_panel.winfo_y() >= edit.photo_panel.winfo_y() + edit.photo_panel.winfo_height()
    assert edit._field_labels["srp"].cget("text") == "SRP (PHP)"
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

    assert all(status.get() == "Not attempted" for status in widget.provider_status_vars.values())


def test_archive_org_provider_status_updates_during_and_after_intake_lookup(form, monkeypatch):
    widget, _root, _photo = form

    class DeferredThread:
        def __init__(self, *, target, **_kwargs):
            self.target = target

        def start(self):
            pass

    monkeypatch.setattr("bookledger.ui.forms.threading.Thread", DeferredThread)
    isbn = "9780553290998"
    widget._set("isbn", isbn)
    widget._lookup_metadata()
    operation_id = widget._active_operation[1]

    widget._set_lookup_provider_status(operation_id, isbn, "Archive.org", "Retrieving from Archive.org…")
    assert widget.provider_status_vars["Archive.org"].get() == "Retrieving from Archive.org…"
    widget._set_lookup_provider_status(operation_id, isbn, "Archive.org", "Metadata retrieved · some fields missing")
    assert widget.provider_status_vars["Archive.org"].get() == "Metadata retrieved · some fields missing"
    widget._finish_lookup(operation_id, isbn, MetadataResult(
        "Retrieved", {"title": "Nightfall", "book_details": "A test synopsis."}, "Archive.org",
        provider_statuses={"Archive.org": "Metadata retrieved · some fields missing"},
    ))
    assert widget.provider_status_vars["Archive.org"].get() == "Metadata retrieved · some fields missing"


def test_bigbook_and_hardcover_provider_status_updates_through_intake(form):
    widget, _root, _photo = form
    widget.metadata_lookup = MetadataLookupService([
        PROVIDERS_BY_NAME["Hardcover"].factory(""),
        PROVIDERS_BY_NAME["Bigbook"].factory(""),
    ])
    widget._sync_provider_statuses()
    widget._set("isbn", "9780306406157")
    widget._active_operation = ("lookup", 13, "9780306406157")
    widget._set_lookup_provider_status(13, "9780306406157", "Bigbook", "Metadata retrieved")
    widget._set_lookup_provider_status(13, "9780306406157", "Hardcover", "Authentication required or failed")
    assert list(widget.provider_status_vars) == ["Hardcover", "Bigbook"]
    assert widget.provider_status_vars["Bigbook"].get() == "Metadata retrieved"
    assert widget.provider_status_vars["Hardcover"].get() == "Authentication required or failed"


def test_provider_status_rows_follow_updated_enabled_provider_order(form, monkeypatch):
    widget, _root, _photo = form
    providers = {provider.name: provider for provider in widget.metadata_lookup.providers}
    widget.metadata_lookup = MetadataLookupService([providers["Booktopia"], providers["Open Library"]])

    class DeferredThread:
        def __init__(self, *, target, **_kwargs):
            self.target = target

        def start(self):
            pass

    monkeypatch.setattr("bookledger.ui.forms.threading.Thread", DeferredThread)
    widget._set("isbn", "9780306406157")
    widget._lookup_metadata()

    assert list(widget.provider_status_vars) == ["Booktopia", "Open Library"]
    assert [widget.metadata_status_panel.grid_slaves(row=row, column=0)[0].cget("text") for row in (1, 2)] == [
        "Booktopia:", "Open Library:",
    ]
    assert all(status.get() == "Not attempted" for status in widget.provider_status_vars.values())


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


def test_photo_preview_and_manual_metadata_values_are_preserved(form, tmp_path):
    widget, root, photo = form
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

    root.deiconify()
    widget.deiconify()
    root.update()
    portrait = tmp_path / "portrait.png"
    Image.new("RGB", (1200, 1800), "blue").save(portrait)
    widget.set_photo(portrait)
    widget.update()
    portrait_size = (widget._photo_image.width(), widget._photo_image.height())
    preview_size = (widget.photo_preview.winfo_width() - 4, widget.photo_preview.winfo_height() - 4)
    assert portrait_size[0] <= preview_size[0] and portrait_size[1] <= preview_size[1]
    assert portrait_size[0] / portrait_size[1] == pytest.approx(2 / 3, abs=0.01)
    assert portrait_size[1] == preview_size[1]

    widget.geometry("1120x850")
    widget.update()
    resized_portrait_size = (widget._photo_image.width(), widget._photo_image.height())
    resized_preview_size = (widget.photo_preview.winfo_width() - 4, widget.photo_preview.winfo_height() - 4)
    assert resized_portrait_size[0] <= resized_preview_size[0]
    assert resized_portrait_size[1] <= resized_preview_size[1]
    assert resized_portrait_size[0] / resized_portrait_size[1] == pytest.approx(2 / 3, abs=0.01)

    landscape = tmp_path / "landscape.png"
    Image.new("RGB", (1800, 1200), "orange").save(landscape)
    widget.set_photo(landscape)
    widget.update()
    landscape_size = (widget._photo_image.width(), widget._photo_image.height())
    preview_size = (widget.photo_preview.winfo_width() - 4, widget.photo_preview.winfo_height() - 4)
    assert landscape_size[0] <= preview_size[0] and landscape_size[1] <= preview_size[1]
    assert landscape_size[0] / landscape_size[1] == pytest.approx(3 / 2, abs=0.01)
    assert landscape_size[0] == preview_size[0]

    widget.geometry("1400x900")
    widget.update()
    resized_landscape_size = (widget._photo_image.width(), widget._photo_image.height())
    resized_preview_size = (widget.photo_preview.winfo_width() - 4, widget.photo_preview.winfo_height() - 4)
    assert resized_landscape_size[0] <= resized_preview_size[0]
    assert resized_landscape_size[1] <= resized_preview_size[1]
    assert resized_landscape_size[0] / resized_landscape_size[1] == pytest.approx(3 / 2, abs=0.01)


def test_shortening_cancel_keeps_active_text_and_saved_versions_unchanged(form, monkeypatch):
    widget, _root, _photo = form
    source = " ".join((
        "Mara returns to the village where she grew up and begins cataloging her grandfather's letters.",
        "She discovers that the family archive connects several generations across the coast.",
        "Each document adds context to a dispute about the old lighthouse and its keepers.",
        "The final chapters follow Mara as she decides what to preserve for the next generation.",
    ))
    widget._set("book_details", source)
    monkeypatch.setattr(widget, "_description_comparison", lambda _original, _shortened: None)

    widget._shorten_book_details()

    assert widget._get("book_details") == source
    assert widget.book_details_original is None
    assert widget.book_details_shortened is None


def test_shortening_and_saved_version_review_require_explicit_selection(form, monkeypatch):
    widget, _root, _photo = form
    source = " ".join((
        "Mara returns to the village where she grew up and begins cataloging her grandfather's letters.",
        "She discovers that the family archive connects several generations across the coast.",
        "Each document adds context to a dispute about the old lighthouse and its keepers.",
        "The final chapters follow Mara as she decides what to preserve for the next generation.",
    ))
    widget._set("book_details", source)
    selected = {}

    def choose_shortened(original, shortened):
        selected["original"] = original
        selected["shortened"] = shortened
        return "shortened"

    monkeypatch.setattr(widget, "_description_comparison", choose_shortened)
    widget._shorten_book_details()

    shortened = selected["shortened"]
    assert selected["original"] == source
    assert shortened and shortened != source
    assert widget._get("book_details") == shortened
    assert widget.book_details_original == source
    assert widget.book_details_shortened == shortened
    assert widget._payload()["book_details_original"] == source
    assert widget._payload()["book_details_shortened"] == shortened

    monkeypatch.setattr(widget, "_description_comparison", lambda _original, _shortened: "original")
    widget._review_book_details()
    assert widget._get("book_details") == source


def test_provider_description_becomes_source_without_automatic_shortening(form):
    widget, _root, _photo = form
    source = " ".join(("A provider synopsis sentence with complete details." * 8).split())

    widget._apply_metadata(MetadataResult("Retrieved", {"book_details": source}, "Google Books"))

    assert widget._get("book_details") == source
    assert widget.book_details_original == source
    assert widget.book_details_shortened is None


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
        _update_description_controls=lambda: None,
    )
    form._get = lambda key: BookForm._get(form, key)
    form._set = lambda key, value: BookForm._set(form, key, value)

    BookForm._apply_metadata(form, MetadataResult("Retrieved", {
        "title": "Provider Title", "author": "Isaac Asimov",
    }, "Booktopia"))

    assert form._get("title") == "Manual Title"
    assert form._get("author") == "Isaac Asimov"


def test_lookup_failure_is_refreshable_but_isbn_miss_is_not(form):
    widget, _root, _photo = form
    widget._set("isbn", "9780306406157")
    widget._set("title", "Keep My Manual Title")
    widget._active_operation = ("lookup", 44, "9780306406157")
    widget._finish_lookup(44, "9780306406157", MetadataResult("Lookup failed", {}, "Open Library", "timeout", "timeout"))
    assert widget.metadata_status.get().startswith("Metadata unavailable")
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

    assert widget.provider_status_vars["Google Books"].get() == "Results returned · ISBN not confirmed"
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
    assert widget.provider_status_vars["Open Library"].get() == "Timed out"
    assert widget.provider_status_vars["Google Books"].get() == "Metadata retrieved · some fields missing"
    assert widget.provider_status_vars["Booktopia"].get() == "Metadata retrieved"


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

    widget.cancel_button.invoke()
    assert not widget.winfo_exists()


def test_incoming_form_cancel_discards_its_capture_without_touching_other_data(
    form, monkeypatch, tmp_path
):
    widget, root, photo = form
    capture_id = "10000000-0000-4000-8000-000000000001"
    incoming_photo = tmp_path / "data" / "incoming" / "batch-test" / f"{capture_id}.jpg"
    incoming_photo.parent.mkdir(parents=True)
    incoming_photo.write_bytes(photo.read_bytes())
    cancelled = []

    def cancel(identifier):
        cancelled.append(identifier)
        incoming_photo.unlink()
        return True

    incoming = BookForm(
        root,
        service=widget.service,
        photo_service=widget.photo_service,
        on_saved=lambda: None,
        initial_isbn="0306406152",
        initial_photo=incoming_photo,
        incoming_capture_id=capture_id,
        on_cancel=cancel,
    )
    monkeypatch.setattr(
        "bookledger.ui.forms.messagebox.askyesno", lambda *_args, **_kwargs: True
    )

    assert incoming._get("isbn") == "0306406152"
    incoming._close()

    assert cancelled == [capture_id]
    assert not incoming_photo.exists()
    assert photo.is_file()


def test_clear_incoming_form_discards_capture_instead_of_detaching_its_metadata(
    form, monkeypatch, tmp_path
):
    widget, root, photo = form
    capture_id = "10000000-0000-4000-8000-000000000002"
    incoming_photo = tmp_path / "data" / "incoming" / "batch-test" / f"{capture_id}.jpg"
    incoming_photo.parent.mkdir(parents=True)
    incoming_photo.write_bytes(photo.read_bytes())
    discarded = []

    def discard(identifier):
        discarded.append(identifier)
        incoming_photo.unlink()
        return True

    incoming = BookForm(
        root,
        service=widget.service,
        photo_service=widget.photo_service,
        on_saved=lambda: None,
        initial_isbn="0306406152",
        initial_photo=incoming_photo,
        incoming_capture_id=capture_id,
        on_discard_incoming=discard,
    )
    monkeypatch.setattr(
        "bookledger.ui.forms.messagebox.askyesno", lambda *_args, **_kwargs: True
    )

    incoming._clear()

    assert discarded == [capture_id]
    assert not incoming_photo.exists()
    assert not incoming.winfo_exists()


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
    assert widget.provider_status_vars["Open Library"].get() == "Not attempted"
    widget._set("isbn", "9780140449136")
    widget._lookup_metadata()
    new_id = widget._active_operation[1]
    widget._finish_lookup(old_id, "9780306406157", MetadataResult("Retrieved", {"title": "Old"}, "Open Library"))

    assert new_id != old_id
    assert widget._get("title") == ""
    assert widget.metadata_status.get() == "Looking up ISBN…"
