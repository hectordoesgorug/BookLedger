import tkinter as tk
from tkinter import ttk
from types import SimpleNamespace
from PIL import Image
import pytest

from bookledger import app as app_module
from bookledger.app import CATALOG_CARD_WIDTH, BookLedgerApp


class FakeTree:
    def __init__(self, clicked="17", selected=("17",)):
        self.clicked = clicked
        self.selected = selected

    def winfo_exists(self):
        return True

    def identify_row(self, _y):
        return self.clicked

    def selection(self):
        return self.selected

    def selection_set(self, item):
        self.selected = (item,)

    def focus(self, item):
        self.focused = item


def test_workspace_clear_drops_tree_reference_before_destroying_children():
    class Child:
        def destroy(self):
            assert subject.tree is None

    subject = SimpleNamespace(tree=FakeTree(), workspace=SimpleNamespace(winfo_children=lambda: [Child()]))
    BookLedgerApp._clear_workspace(subject)
    assert subject.tree is None


def test_legacy_sales_page_name_resolves_to_sale_history():
    captured = {}
    subject = SimpleNamespace(
        current_page=None,
        page_title=SimpleNamespace(configure=lambda **options: captured.update(options)),
        _clear_workspace=lambda: None,
        _build_sales=lambda: captured.setdefault("built", True),
    )

    BookLedgerApp.show_page(subject, "Sales")

    assert subject.current_page == "Sale History"
    assert captured == {"text": "Sale History", "built": True}


def test_double_click_uses_the_matching_active_tree_row():
    opened = []
    tree = FakeTree(clicked="17", selected=("17",))
    subject = SimpleNamespace(tree=tree, open_selected_edit=opened.append)
    event = SimpleNamespace(widget=tree, y=42)

    result = BookLedgerApp._on_tree_double_click(subject, event)

    assert result == "break"
    assert opened == [17]


def test_double_click_rejects_stale_tree_or_mismatched_selection():
    opened = []
    old_tree = FakeTree()
    subject = SimpleNamespace(tree=FakeTree(), open_selected_edit=opened.append)
    assert BookLedgerApp._on_tree_double_click(subject, SimpleNamespace(widget=old_tree, y=42)) == "break"

    mismatched_tree = FakeTree(clicked="17", selected=("18",))
    subject.tree = mismatched_tree
    assert BookLedgerApp._on_tree_double_click(subject, SimpleNamespace(widget=mismatched_tree, y=42)) == "break"
    assert opened == []


def test_physical_copy_label_uses_record_copy_number_not_internal_id():
    assert BookLedgerApp._physical_copy_label({"copy_id": 41, "copy_number": 1}) == "Copy 1"
    assert BookLedgerApp._physical_copy_label({"copy_id": 42, "copy_number": 2}) == "Copy 2"


def test_inventory_rows_include_physical_copy_number():
    class InventoryTree:
        def __init__(self):
            self.rows = []

        def winfo_exists(self):
            return True

        def get_children(self):
            return tuple(iid for iid, _values in self.rows)

        def delete(self, *_items):
            self.rows.clear()

        def insert(self, _parent, _index, *, iid, values, tags=()):
            self.rows.append((iid, values, tags))

    records = [
        {"copy_id": 41, "copy_code": "BL-000041", "copy_number": 1, "title": "Shared Title", "author": "Author", "format": "Paperback", "condition": "Good", "location": "Shelf", "display_price_minor": 10000, "status": "Available"},
        {"copy_id": 42, "copy_code": "BL-000042", "copy_number": 2, "title": "Shared Title", "author": "Author", "format": "Paperback", "condition": "Good", "location": "Shelf", "display_price_minor": 10000, "status": "Available"},
    ]
    subject = SimpleNamespace(
        catalog=SimpleNamespace(list_copies=lambda *_args: records),
        global_search=SimpleNamespace(get=lambda: ""), status_filter=SimpleNamespace(get=lambda: "All"),
        genre_filter=SimpleNamespace(get=lambda: "All"), condition_filter=SimpleNamespace(get=lambda: "All"),
        location_filter=SimpleNamespace(get=lambda: "All"), _catalog_inventory=True,
        _inventory_sort_column="title", _inventory_sort_reverse=False, tree=InventoryTree(),
        _inventory_status_tags={"Available": "inventory_status_available"},
        _sold_last_sort=BookLedgerApp._sold_last_sort, money=BookLedgerApp.money,
        status_var=SimpleNamespace(set=lambda _text: None),
    )

    BookLedgerApp._populate_catalog(subject)

    assert [entry[1][1] for entry in subject.tree.rows] == [1, 2]
    assert all(entry[2] == ("inventory_status_available",) for entry in subject.tree.rows)


def test_explicit_copy_id_does_not_read_tree_selection(monkeypatch):
    class StaleTree:
        def selection(self):
            raise AssertionError("explicit Copy ID must not consult old Treeview selection")

    selected = []
    row = {"copy_id": 17, "title": "Selected Copy"}
    subject = SimpleNamespace(
        tree=StaleTree(),
        status_var=SimpleNamespace(set=lambda _message: None),
        catalog=SimpleNamespace(get_copy=lambda copy_id: row if copy_id == 17 else None),
        photos=object(),
        _after_save=lambda _message: None,
    )
    monkeypatch.setattr(app_module, "BookForm", lambda *args, **kwargs: selected.append(kwargs["existing"]))

    BookLedgerApp.open_selected_edit(subject, 17)

    assert selected == [row]


def test_inventory_right_click_targets_clicked_copy_and_selects_it():
    tree = FakeTree(clicked="42", selected=("17",))
    opened = []
    subject = SimpleNamespace(
        tree=tree,
        current_page="Inventory",
        show_copy_context_menu=lambda copy_id, x, y: opened.append((copy_id, x, y)),
    )
    event = SimpleNamespace(widget=tree, y=55, x_root=300, y_root=400)
    assert BookLedgerApp._on_inventory_right_click(subject, event) == "break"
    assert tree.selection() == ("42",)
    assert tree.focused == "42"
    assert opened == [(42, 300, 400)]


def test_context_menu_has_approved_options_order_and_disabled_current_status(monkeypatch):
    captured = {}

    class FakeMenu:
        def __init__(self, *_args, **_kwargs):
            self.entries = []
            captured["menu"] = self

        def add_command(self, **kwargs):
            self.entries.append(kwargs)

        def tk_popup(self, x, y):
            self.position = (x, y)

        def grab_release(self):
            pass

    monkeypatch.setattr(app_module.tk, "Menu", FakeMenu)
    row = {"copy_id": 42, "copy_code": "BL-000042", "title": "A Book", "status": "Listed"}
    subject = SimpleNamespace(
        catalog=SimpleNamespace(get_copy=lambda copy_id: row if copy_id == 42 else None),
        status_var=SimpleNamespace(set=lambda _text: None),
        open_copy_details=lambda copy_id: captured.setdefault("view", copy_id),
        open_selected_edit=lambda copy_id: captured.setdefault("edit", copy_id),
        _poster_not_implemented=lambda: None,
        _change_copy_status=lambda copy_id, status: None,
        _confirm_delete_not_implemented=lambda copy_id: None,
    )
    BookLedgerApp.show_copy_context_menu(subject, 42, 10, 20)
    menu = captured["menu"]
    assert [entry["label"] for entry in menu.entries] == [
        "View Details", "Create Poster", "Mark as Available", "Mark as Listed",
        "Mark as Not for Sale", "Mark as Sold", "Edit Book", "Delete Book",
    ]
    assert menu.entries[3]["state"] == "disabled"
    menu.entries[0]["command"]()
    menu.entries[6]["command"]()
    assert captured["view"] == 42
    assert captured["edit"] == 42


def test_inventory_context_menu_is_not_invoked_on_other_pages():
    tree = FakeTree(clicked="42")
    opened = []
    subject = SimpleNamespace(tree=tree, current_page="Dashboard", show_copy_context_menu=opened.append)
    assert BookLedgerApp._on_inventory_right_click(subject, SimpleNamespace(widget=tree, y=55)) == "break"
    assert opened == []


def test_sold_last_sort_preserves_the_requested_order_inside_each_group():
    rows = [
        {"copy_id": 1, "status": "Sold", "price": 5},
        {"copy_id": 2, "status": "Available", "price": 8},
        {"copy_id": 3, "status": "Listed", "price": 2},
        {"copy_id": 4, "status": "Sold", "price": 1},
    ]
    sorted_rows = BookLedgerApp._sold_last_sort(rows, lambda row: row["price"])
    assert [row["copy_id"] for row in sorted_rows] == [3, 2, 4, 1]


def test_sold_thumbnail_gets_gray_overlay_only_when_sold():
    cover = Image.new("RGB", (2, 2), "#ff0000")
    assert BookLedgerApp._sold_thumbnail(cover, "Available") is cover
    sold = BookLedgerApp._sold_thumbnail(cover, "Sold")
    assert sold.getpixel((0, 0)) != cover.getpixel((0, 0))
    assert sold.getpixel((0, 0))[0] < 255 and sold.getpixel((0, 0))[1] > 0


def test_catalog_thumbnail_indicator_follows_physical_copy_status():
    assert BookLedgerApp._catalog_thumbnail_indicator("Available") is None
    assert BookLedgerApp._catalog_thumbnail_indicator("Listed") is None
    assert BookLedgerApp._catalog_thumbnail_indicator("Not for Sale") == "lock"
    assert BookLedgerApp._catalog_thumbnail_indicator("Sold") == "sold"


def test_catalog_grid_reflows_fixed_width_cards_when_width_changes():
    class Cards:
        def __init__(self):
            self.columns = {}

        def grid_columnconfigure(self, column, **options):
            self.columns[column] = options

    class Card:
        def __init__(self):
            self.positions = []

        def grid(self, **options):
            self.positions.append(options)

    subject = SimpleNamespace(
        _catalog_card_widgets=[Card() for _ in range(5)],
        _catalog_grid_columns=0,
        catalog_cards=Cards(),
    )

    BookLedgerApp._layout_catalog_cards(subject, 700)
    assert [card.positions[-1]["column"] for card in subject._catalog_card_widgets] == [0, 1, 0, 1, 0]
    assert subject._catalog_grid_columns == 2

    BookLedgerApp._layout_catalog_cards(subject, 340)
    assert [card.positions[-1]["column"] for card in subject._catalog_card_widgets] == [0, 0, 0, 0, 0]
    assert subject._catalog_grid_columns == 1
    assert subject.catalog_cards.columns[1]["weight"] == 0


def test_catalog_grid_renders_fixed_width_cards_left_aligned_at_responsive_sizes():
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"Tk widget geometry tests require a display: {exc}")
    try:
        root.geometry("760x420+0+0")
        container = ttk.Frame(root)
        container.pack(fill="both", expand=True)
        subject = SimpleNamespace(
            _catalog_card_widgets=[],
            _catalog_grid_columns=0,
            after_idle=root.after_idle,
        )
        subject._queue_catalog_layout = lambda canvas, width: BookLedgerApp._queue_catalog_layout(subject, canvas, width)
        subject._apply_pending_catalog_layout = lambda: BookLedgerApp._apply_pending_catalog_layout(subject)
        subject._layout_catalog_cards = lambda width: BookLedgerApp._layout_catalog_cards(subject, width)
        BookLedgerApp._build_catalog_grid(subject, container)
        canvas = subject.catalog_canvas
        cards = subject.catalog_cards
        root.update()
        widgets = []
        for index in range(4):
            card = ttk.LabelFrame(cards, text=f"BL-{index + 1}", width=CATALOG_CARD_WIDTH, padding=8)
            tk.Frame(card, width=CATALOG_CARD_WIDTH - 40, height=180).pack(fill="x")
            ttk.Label(card, text="A book title", wraplength=CATALOG_CARD_WIDTH - 40).pack(anchor="w")
            widgets.append(card)
        subject._catalog_card_widgets = widgets
        for card in widgets:
            BookLedgerApp._fix_catalog_card_geometry(card)
        BookLedgerApp._layout_catalog_cards(subject, canvas.winfo_width())
        root.update()

        assert subject._catalog_grid_columns == 2
        assert cards.winfo_width() == min(canvas.winfo_width(), 2 * (CATALOG_CARD_WIDTH + 14))
        assert all(abs(card.winfo_width() - CATALOG_CARD_WIDTH) <= 1 for card in widgets)
        assert widgets[0].winfo_x() < 20
        assert widgets[1].winfo_x() > widgets[0].winfo_x()

        root.geometry("360x420+0+0")
        root.update()
        assert subject._catalog_grid_columns == 1
        assert cards.winfo_width() == min(canvas.winfo_width(), CATALOG_CARD_WIDTH + 14)
        assert all(abs(card.winfo_width() - CATALOG_CARD_WIDTH) <= 1 for card in widgets)
        assert widgets[0].winfo_x() < 20

        root.geometry("1000x650+0+0")
        root.update()
        assert subject._catalog_grid_columns == 2
        assert cards.winfo_width() == min(canvas.winfo_width(), 2 * (CATALOG_CARD_WIDTH + 14))
        assert all(abs(card.winfo_width() - CATALOG_CARD_WIDTH) <= 1 for card in widgets)
        assert widgets[0].winfo_x() < 20
    finally:
        root.destroy()


def test_status_menu_prompts_only_for_not_for_sale_or_sold_departures(monkeypatch):
    prompts = []
    actions = []
    row = {"copy_id": 42, "copy_code": "BL-000042", "title": "A Book", "status": "Available"}
    subject = SimpleNamespace(
        catalog=SimpleNamespace(
            get_copy=lambda _copy_id: dict(row),
            status_change_requires_confirmation=app_module.CatalogService.status_change_requires_confirmation,
            change_status=lambda copy_id, status: actions.append((copy_id, status)),
        ),
        status_var=SimpleNamespace(set=lambda _text: None),
        _after_save=lambda message: actions.append(message),
    )
    monkeypatch.setattr(app_module.messagebox, "askyesno", lambda *args, **kwargs: prompts.append(args) or False)
    BookLedgerApp._change_copy_status(subject, 42, "Listed")
    assert prompts == []
    assert actions[0] == (42, "Listed")

    actions.clear()
    row["status"] = "Not for Sale"
    BookLedgerApp._change_copy_status(subject, 42, "Available")
    assert len(prompts) == 1
    assert actions == []


def test_cancelling_sold_status_change_explains_sale_void_and_preserves_state(monkeypatch):
    changes = []
    row = {"copy_code": "BL-000042", "title": "A Book", "status": "Sold"}
    subject = SimpleNamespace(
        catalog=SimpleNamespace(
            get_copy=lambda _copy_id: row,
            status_change_requires_confirmation=app_module.CatalogService.status_change_requires_confirmation,
            change_status=lambda copy_id, status, **kwargs: changes.append((copy_id, status, kwargs)),
        ),
        status_var=SimpleNamespace(set=lambda _message: None),
        _after_save=lambda _message: None,
        _ask_sale_void_reason=lambda _row, _status: None,
    )
    monkeypatch.setattr(BookLedgerApp, "_ask_sale_void_reason", lambda *_args: None)

    BookLedgerApp._change_copy_status(subject, 42, "Available")

    assert changes == []
    assert row["status"] == "Sold"


def test_confirmed_sold_status_change_invokes_atomic_service(monkeypatch):
    changes = []
    subject = SimpleNamespace(
        catalog=SimpleNamespace(
            get_copy=lambda _copy_id: {"copy_code": "BL-000042", "title": "A Book", "status": "Sold"},
            status_change_requires_confirmation=app_module.CatalogService.status_change_requires_confirmation,
            change_status=lambda copy_id, status, **kwargs: changes.append((copy_id, status, kwargs)),
        ),
        _after_save=lambda _message: None,
        _ask_sale_void_reason=lambda _row, _status: "Returned Order",
    )
    monkeypatch.setattr(BookLedgerApp, "_ask_sale_void_reason", lambda *_args: "Returned Order")

    BookLedgerApp._change_copy_status(subject, 42, "Listed")

    assert changes == [(42, "Listed", {"void_reason": "Returned Order"})]


def test_view_details_formats_complete_sale_and_void_log_without_fabricating_active_void_data():
    subject = SimpleNamespace(money=lambda amount: f"PHP {amount}")
    history = [
        {"sale_id": 101, "sale_date": "2026-10-19", "price_minor": 12000, "voided_at": "2026-10-20T12:00:00Z", "void_reason": "Cancelled Order"},
        {"sale_id": 102, "sale_date": "2026-10-21", "price_minor": 15000, "voided_at": None, "void_reason": None},
    ]

    rendered = BookLedgerApp._sale_history_text(subject, history)

    assert "Sale 1 — Voided" in rendered
    assert "Transaction ID: 101" in rendered
    assert "Sale Voided: 2026-10-20T12:00:00Z" in rendered
    assert "Reason: Cancelled Order" in rendered
    assert "Original Price: PHP 12000" in rendered
    assert "Sale 2 — Completed" in rendered
    assert "Date Sold: 2026-10-21" in rendered
    assert "Original Price: PHP 15000" in rendered
    assert "Sale Voided:" not in rendered.split("Sale 2 — Completed", 1)[1]


def test_delete_confirmation_moves_selected_copy_to_trash(monkeypatch):
    confirmations = []
    deleted = []
    refreshed = []
    subject = SimpleNamespace(
        catalog=SimpleNamespace(get_copy=lambda _copy_id: {"copy_code": "BL-000042", "title": "A Book"}),
        lifecycle=SimpleNamespace(trash_copy=lambda copy_id: deleted.append(copy_id)),
        status_var=SimpleNamespace(set=lambda message: refreshed.append(message)),
        _after_save=lambda message: refreshed.append(message),
    )
    monkeypatch.setattr(app_module.messagebox, "askyesno", lambda *args, **kwargs: confirmations.append(args) or True)
    BookLedgerApp._confirm_delete(subject, 42)
    assert "BL-000042" in confirmations[0][1]
    assert deleted == [42]
