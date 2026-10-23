import tkinter as tk
from tkinter import ttk
from types import SimpleNamespace
from PIL import Image
import pytest

from bookledger import app as app_module
from bookledger.app import CATALOG_CARD_WIDTH, BookLedgerApp
from bookledger.config_store import AppConfigStore


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


def test_hover_tooltip_is_screen_clamped_and_stays_outside_parent_layout(monkeypatch):
    class Tip:
        def __init__(self, parent):
            self.parent = parent
            self.geometry = None
            self.overrideredirect = False
            self.attributes = {}

        def wm_overrideredirect(self, value):
            self.overrideredirect = value

        def wm_attributes(self, name, value):
            self.attributes[name] = value

        def wm_geometry(self, value):
            self.geometry = value

        def update_idletasks(self):
            pass

        def winfo_reqwidth(self):
            return 300

        def winfo_reqheight(self):
            return 100

        def winfo_screenwidth(self):
            return 1920

        def winfo_screenheight(self):
            return 1080

    class Label:
        def __init__(self, *_args, **_kwargs):
            pass

        def pack(self):
            pass

    tips = []
    monkeypatch.setattr(app_module.tk, "Toplevel", lambda parent: tips.append(Tip(parent)) or tips[-1])
    monkeypatch.setattr(app_module.ttk, "Label", Label)
    parent = object()
    subject = SimpleNamespace(
        _hover_tooltip=None,
        _hide_hover_tooltip=lambda _event=None: None,
        winfo_toplevel=lambda: parent,
    )
    event = SimpleNamespace(x_root=1915, y_root=1075)

    BookLedgerApp._show_hover_tooltip(subject, event, "Full explanation remains available")

    assert subject._hover_tooltip.overrideredirect
    assert subject._hover_tooltip.parent is parent
    assert subject._hover_tooltip.attributes["-topmost"]
    assert subject._hover_tooltip.geometry == "+1603+963"


def test_tooltip_uses_floating_window_without_managing_parent_layout(monkeypatch):
    events = []

    class Tip:
        def __init__(self, parent):
            self.parent = parent

        def wm_overrideredirect(self, _value):
            pass

        def wm_attributes(self, *_args):
            pass

        def wm_geometry(self, _value):
            pass

        def update_idletasks(self):
            pass

        def winfo_reqwidth(self):
            return 100

        def winfo_reqheight(self):
            return 60

        def winfo_screenwidth(self):
            return 1280

        def winfo_screenheight(self):
            return 800

    class Label:
        def __init__(self, parent, **_kwargs):
            events.append(("label-parent", parent))

        def pack(self):
            events.append(("pack-tooltip-label",))

    root = object()
    panel = object()
    monkeypatch.setattr(app_module.tk, "Toplevel", lambda parent: events.append(("toplevel-parent", parent)) or Tip(parent))
    monkeypatch.setattr(app_module.ttk, "Label", Label)
    subject = SimpleNamespace(
        _hover_tooltip=None,
        _hide_hover_tooltip=lambda _event=None: None,
        winfo_toplevel=lambda: root,
    )

    BookLedgerApp._show_hover_tooltip(subject, SimpleNamespace(x_root=100, y_root=100), "Help")

    assert subject._hover_tooltip.parent is root
    assert events == [("toplevel-parent", root), ("label-parent", subject._hover_tooltip), ("pack-tooltip-label",)]
    assert all(panel is not event for event in events)


def test_tooltip_wraps_inside_available_panel_space_to_avoid_adjacent_controls(monkeypatch):
    captured = {}

    class Tip:
        def __init__(self, _parent):
            pass

        def wm_overrideredirect(self, _value):
            pass

        def wm_attributes(self, *_args):
            pass

        def wm_geometry(self, value):
            captured["geometry"] = value

        def update_idletasks(self):
            pass

        def winfo_reqwidth(self):
            return captured["wraplength"] + 16

        def winfo_reqheight(self):
            return 80

        def winfo_screenwidth(self):
            return 1280

        def winfo_screenheight(self):
            return 800

    class Label:
        def __init__(self, _parent, *, wraplength, **_kwargs):
            captured["wraplength"] = wraplength

        def pack(self):
            pass

    panel = SimpleNamespace(winfo_width=lambda: 494, winfo_rootx=lambda: 246)
    widget = SimpleNamespace(_tooltip_bounds=panel)
    monkeypatch.setattr(app_module.tk, "Toplevel", Tip)
    monkeypatch.setattr(app_module.ttk, "Label", Label)
    subject = SimpleNamespace(
        _hover_tooltip=None,
        _hide_hover_tooltip=lambda _event=None: None,
        winfo_toplevel=lambda: object(),
    )

    BookLedgerApp._show_hover_tooltip(subject, SimpleNamespace(x_root=493, y_root=198, widget=widget), "Readable help")

    assert captured["wraplength"] == 215
    assert captured["geometry"] == "+505+210"
    assert int(captured["geometry"].split("+")[1]) + captured["wraplength"] + 16 <= 740


def test_preferences_delete_tooltip_has_no_info_icon_and_preserves_row_geometry():
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"Tk UI geometry test requires Tcl/Tk: {exc}")
    root.geometry("1000x700")
    root._hide_hover_tooltip = lambda event=None: BookLedgerApp._hide_hover_tooltip(root, event)
    parent = ttk.Frame(root, padding=12)
    parent.pack(fill="both", expand=True)
    subject = SimpleNamespace(
        _show_hover_tooltip=lambda event, message: BookLedgerApp._show_hover_tooltip(root, event, message),
        _hide_hover_tooltip=lambda event=None: BookLedgerApp._hide_hover_tooltip(root, event),
    )
    try:
        def geometry(widget):
            return (widget.winfo_rootx(), widget.winfo_rooty(), widget.winfo_width(), widget.winfo_height())

        for index, (title, kind) in enumerate((
            ("Genre", "genre"),
            ("Format", "format"),
            ("Location", "location"),
        )):
            BookLedgerApp._build_value_list_editor(
                subject,
                parent,
                title,
                kind,
                lambda: ["Assigned value", "Unassigned value"],
                lambda value: int(value == "Assigned value"),
                lambda value: value,
                lambda old, new: new,
                lambda _value: None,
                row=index,
                column=0,
            )
        root.update()
        for title in ("Genre", "Format", "Location"):
            panel = next(child for child in parent.winfo_children() if isinstance(child, ttk.LabelFrame) and child.cget("text") == title)
            list_frame = next(child for child in panel.winfo_children() if isinstance(child, ttk.Frame))
            canvas = next(child for child in list_frame.winfo_children() if isinstance(child, tk.Canvas))
            rows = next(child for child in canvas.winfo_children() if isinstance(child, ttk.Frame))
            assigned_row, unassigned_row = rows.winfo_children()
            assigned_buttons = {child.cget("text"): child for child in assigned_row.winfo_children() if isinstance(child, ttk.Button)}
            unassigned_buttons = {child.cget("text"): child for child in unassigned_row.winfo_children() if isinstance(child, ttk.Button)}
            assert not any(
                isinstance(child, ttk.Label) and child.cget("text") == "ⓘ"
                for row in (assigned_row, unassigned_row)
                for child in row.winfo_children()
            ), f"{title} rows should not contain redundant information icons"
            assert str(assigned_buttons["Delete"].cget("state")) == "disabled"
            assert str(unassigned_buttons["Delete"].cget("state")) == "normal"
            for name in ("Rename", "Delete"):
                assert geometry(assigned_buttons[name])[0] == geometry(unassigned_buttons[name])[0]
                assert geometry(assigned_buttons[name])[2:] == geometry(unassigned_buttons[name])[2:]

            buttons = assigned_buttons
            before = {name: geometry(buttons[name]) for name in ("Rename", "Delete")}
            delete_button = buttons["Delete"]
            event = SimpleNamespace(x_root=delete_button.winfo_rootx(), y_root=delete_button.winfo_rooty(), widget=delete_button)
            BookLedgerApp._show_hover_tooltip(root, event, f"{title} assignments remain protected.")
            root.update()
            visible = {name: geometry(buttons[name]) for name in ("Rename", "Delete")}
            assert root._hover_tooltip.winfo_exists()
            assert "assignments remain protected" in root._hover_tooltip.winfo_children()[0].cget("text")
            assert visible == before, f"{title} row moved while its tooltip was visible"

            BookLedgerApp._hide_hover_tooltip(root)
            root.update()
            hidden = {name: geometry(buttons[name]) for name in ("Rename", "Delete")}
            assert hidden == before, f"{title} row moved after its tooltip was dismissed"
    finally:
        root.destroy()


def test_customize_section_uses_two_equal_button_columns_and_full_width_url_entry():
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"Tk UI geometry test requires Tcl/Tk: {exc}")
    root.geometry("1000x700")
    parent = ttk.Frame(root, padding=12)
    parent.pack(fill="both", expand=True)
    catalog = SimpleNamespace()
    for name, values in {
        "list_genres": [], "list_formats": [], "list_locations": [],
    }.items():
        setattr(catalog, name, lambda values=values: values)
    for name in (
        "value_assignment_count", "location_assignment_count",
    ):
        setattr(catalog, name, lambda *_args: 0)
    for name in ("add_genre", "rename_genre", "delete_genre", "add_format", "rename_format", "delete_format", "add_location", "rename_location", "delete_location"):
        setattr(catalog, name, lambda *_args: None)
    subject = SimpleNamespace(
        catalog=catalog,
        config_store=SimpleNamespace(get=lambda *_args: ""),
        _available_theme_names=("clam", "flatly"),
        _active_theme="clam",
        _apply_theme_selection=lambda: None,
        _show_hover_tooltip=lambda *_args: None,
        _hide_hover_tooltip=lambda *_args: None,
        _change_shop_logo=lambda: None,
        _clear_shop_logo=lambda: None,
        _save_shop_url=lambda: None,
        _clear_shop_url=lambda: None,
    )
    subject._build_value_list_editor = lambda *args, **kwargs: BookLedgerApp._build_value_list_editor(subject, *args, **kwargs)

    try:
        BookLedgerApp._build_preferences(subject, parent)
        root.update()
        customize = next(child for child in parent.winfo_children() if isinstance(child, ttk.LabelFrame) and child.cget("text") == "Customize")
        buttons = {child.cget("text"): child for child in customize.winfo_children() if isinstance(child, ttk.Button)}
        theme_selector = subject.theme_selector
        assert str(theme_selector.cget("state")) == "readonly"
        assert tuple(theme_selector.cget("values")) == subject._available_theme_names
        assert subject.theme_var.get() == "clam"
        names = ("Change Logo", "Clear Logo", "Add Logo Link", "Clear Logo Link")
        assert set(names) <= set(buttons)
        assert {buttons[name].cget("width") for name in names} == {16}
        assert len({buttons[name].winfo_height() for name in names}) == 1
        assert buttons["Change Logo"].grid_info()["row"] == buttons["Clear Logo"].grid_info()["row"]
        assert buttons["Add Logo Link"].grid_info()["row"] == buttons["Clear Logo Link"].grid_info()["row"]
        assert buttons["Change Logo"].winfo_rootx() < buttons["Clear Logo"].winfo_rootx()
        assert buttons["Add Logo Link"].winfo_rootx() < buttons["Clear Logo Link"].winfo_rootx()
        url_entry = subject.shop_url_entry
        assert url_entry.grid_info()["row"] == 5
        assert url_entry.grid_info()["columnspan"] == 2
        assert url_entry.winfo_width() > buttons["Change Logo"].winfo_width()
    finally:
        root.destroy()


def test_theme_selection_applies_only_supported_names_and_persists_for_restart(tmp_path):
    class Value:
        def __init__(self, value):
            self.value = value

        def get(self):
            return self.value

        def set(self, value):
            self.value = value

    class ThemeStyle:
        def __init__(self):
            self.current = "clam"

        def theme_use(self, name=None):
            if name is None:
                return self.current
            if name not in ("clam", "flatly", "darkly"):
                raise tk.TclError(name)
            self.current = name
            return name

    config_path = tmp_path / "config.json"
    store = AppConfigStore(config_path)
    store.set(("preferences", "shop_url"), "https://shop.example/books")
    style = ThemeStyle()
    status = Value("")
    subject = SimpleNamespace(
        theme_var=Value("flatly"),
        theme_style=style,
        _available_theme_names=("clam", "flatly", "darkly"),
        config_store=store,
        status_var=status,
        _configure_style=lambda: None,
    )

    assert BookLedgerApp._apply_theme_selection(subject)
    assert style.theme_use() == "flatly"
    reloaded = AppConfigStore(config_path)
    assert reloaded.get(("preferences", "theme")) == "flatly"
    assert reloaded.get(("preferences", "shop_url")) == "https://shop.example/books"
    assert app_module.resolve_theme_name(
        subject._available_theme_names,
        reloaded.get(("preferences", "theme")),
        "clam",
    ) == "flatly"

    subject.theme_var.set("unsupported-theme")
    assert not BookLedgerApp._apply_theme_selection(subject)
    assert style.theme_use() == "flatly"
    assert reloaded.get(("preferences", "theme")) == "flatly"

    store.set(("preferences", "theme"), "missing-theme")
    assert app_module.resolve_theme_name(subject._available_theme_names, "missing-theme", "clam") == "clam"
    assert AppConfigStore(config_path).get(("preferences", "theme")) == "missing-theme"


def test_navigation_icons_use_uniform_larger_geometry():
    assert app_module.NAV_ICON_FRAME_SIZE == 36
    assert len(set(app_module.NAV_ICON_CONTENT_SIZES)) == 3
    assert min(app_module.NAV_ICON_CONTENT_SIZES) >= 26
    for _name, filename, _fallback in app_module.NAVIGATION_ITEMS:
        image = app_module.render_svg_icon(
            app_module.resource_path("assets", filename),
            frame_size=app_module.NAV_ICON_FRAME_SIZE,
            content_size=app_module.NAV_ICON_CONTENT_SIZES[0],
        )
        assert image is not None
        assert image.size == (36, 36)
        assert image.getbbox() is not None


def test_navigation_active_style_and_hover_animation_restore_without_layout_changes():
    class Scheduler:
        def __init__(self):
            self.jobs = {}
            self.serial = 0

        def after(self, _delay, callback):
            self.serial += 1
            self.jobs[self.serial] = callback
            return self.serial

        def after_cancel(self, job_id):
            self.jobs.pop(job_id, None)

        def finish(self):
            while self.jobs:
                job_id = next(iter(self.jobs))
                self.jobs.pop(job_id)()

    class Button:
        def __init__(self, images):
            self._nav_frame_images = images
            self._nav_frame_index = 0
            self._nav_animation_after_id = None
            self.current_image = images[0]
            self.styles = []

        def configure(self, **kwargs):
            if "image" in kwargs:
                self.current_image = kwargs["image"]
            if "style" in kwargs:
                self.styles.append(kwargs["style"])

        def winfo_exists(self):
            return True

    scheduler = Scheduler()
    images = (object(), object(), object())
    catalog = Button(images)
    settings = Button(images)
    subject = SimpleNamespace(
        after=scheduler.after,
        after_cancel=scheduler.after_cancel,
        current_page="Catalog",
        nav_buttons={"Catalog": catalog, "Settings": settings},
    )

    BookLedgerApp._update_active_navigation(subject)
    assert catalog.styles[-1] == "SidebarActive.TButton"
    assert settings.styles[-1] == "Sidebar.TButton"

    BookLedgerApp._animate_navigation_button(subject, catalog, 2)
    scheduler.finish()
    assert catalog._nav_frame_index == 2
    assert catalog.current_image is images[2]
    BookLedgerApp._animate_navigation_button(subject, catalog, 0)
    scheduler.finish()
    assert catalog._nav_frame_index == 0
    assert catalog.current_image is images[0]


def test_shop_url_save_and_logo_click_preserve_config_and_only_open_web_urls(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    config_path.write_text('{"other":{"keep":true}}', encoding="utf-8")
    store = AppConfigStore(config_path)

    class Value:
        def __init__(self, value=""):
            self.value = value

        def get(self):
            return self.value

        def set(self, value):
            self.value = value

    subject = SimpleNamespace(
        config_store=store,
        shop_url_var=Value("shop.example/store"),
        status_var=Value(),
    )
    subject._logo_url = lambda: BookLedgerApp._logo_url(subject)
    assert BookLedgerApp._save_shop_url(subject)
    assert subject.shop_url_var.get() == "https://shop.example/store"
    saved = __import__("json").loads(config_path.read_text(encoding="utf-8"))
    assert saved["other"] == {"keep": True}
    assert saved["preferences"]["shop_url"] == "https://shop.example/store"

    opened = []
    monkeypatch.setattr(app_module.webbrowser, "open", lambda url, new: opened.append((url, new)) or True)
    assert BookLedgerApp._open_shop_link(subject)
    assert opened == [("https://shop.example/store", 2)]
    store.set(("preferences", "shop_url"), "file:///C:/Windows/system.ini")
    assert not BookLedgerApp._open_shop_link(subject)
    assert opened == [("https://shop.example/store", 2)]
    store.set(("preferences", "shop_url"), "")
    assert not BookLedgerApp._open_shop_link(subject)


def test_custom_shop_logo_selection_is_saved_as_a_relative_portable_asset(tmp_path, monkeypatch):
    source = tmp_path / "shop.png"
    Image.new("RGBA", (1400, 700), (30, 90, 160, 255)).save(source)
    data = tmp_path / "portable" / "data"
    store = AppConfigStore(tmp_path / "portable" / "config.json")
    selected = [str(source)]
    monkeypatch.setattr(app_module.filedialog, "askopenfilename", lambda **_kwargs: selected[0])

    class Status:
        def set(self, _value):
            pass

    subject = SimpleNamespace(
        paths=SimpleNamespace(data=data, assets=data / "assets"),
        config_store=store,
        status_var=Status(),
        _refresh_brand_logo=lambda: None,
    )

    assert BookLedgerApp._change_shop_logo(subject)
    first_reference = store.get(("preferences", "shop_logo_path"))
    assert first_reference.startswith("assets/shop-logo-") and first_reference.endswith(".png")
    first_path = data / first_reference
    assert first_path.is_file()
    with Image.open(first_path) as image:
        assert image.size == (1024, 512)

    replacement = tmp_path / "replacement.jpg"
    Image.new("RGB", (300, 900), "orange").save(replacement)
    selected[0] = str(replacement)
    assert BookLedgerApp._change_shop_logo(subject)
    second_reference = store.get(("preferences", "shop_logo_path"))
    assert second_reference != first_reference
    assert (data / second_reference).is_file()
    assert first_path.is_file()


def test_clear_shop_logo_restores_default_persists_and_keeps_managed_asset(tmp_path, monkeypatch):
    data = tmp_path / "data"
    assets = data / "assets"
    assets.mkdir(parents=True)
    custom_logo = assets / "shop-logo-kept.png"
    Image.new("RGB", (100, 50), "blue").save(custom_logo)
    config_path = tmp_path / "config.json"
    store = AppConfigStore(config_path)
    store.set(("preferences", "shop_logo_path"), "assets/shop-logo-kept.png")
    refreshes = []

    class Status:
        def set(self, _value):
            pass

    subject = SimpleNamespace(
        config_store=store,
        paths=SimpleNamespace(data=data),
        status_var=Status(),
        _refresh_brand_logo=lambda: refreshes.append(True),
    )

    assert BookLedgerApp._clear_shop_logo(subject)
    assert refreshes == [True]
    assert custom_logo.is_file()
    assert AppConfigStore(config_path).get(("preferences", "shop_logo_path"), "") == ""

    # A fresh store models restart: an empty selection loads the bundled default.
    loaded_sizes = []
    monkeypatch.setattr(app_module.ImageTk, "PhotoImage", lambda image, master: loaded_sizes.append(image.size) or object())
    subject.config_store = AppConfigStore(config_path)
    subject.brand_logo_label = SimpleNamespace(
        configure=lambda **_kwargs: None,
        pack_forget=lambda: None,
        pack=lambda **_kwargs: None,
        winfo_manager=lambda: "pack",
    )
    BookLedgerApp._refresh_brand_logo(subject)
    with Image.open(app_module.resource_path("assets", "generalists_bookshop_logo.png")) as default:
        default.thumbnail((176, 66), Image.Resampling.LANCZOS)
        assert loaded_sizes == [default.size]


def test_clear_shop_link_persists_across_restart_and_sidebar_logo_does_not_open_browser(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    store = AppConfigStore(config_path)
    store.set(("preferences", "shop_url"), "https://shop.example/books")

    class Value:
        def __init__(self, value):
            self.value = value

        def get(self):
            return self.value

        def set(self, value):
            self.value = value

    class Status:
        def set(self, _value):
            pass

    subject = SimpleNamespace(config_store=store, shop_url_var=Value("https://shop.example/books"), status_var=Status())
    assert BookLedgerApp._clear_shop_url(subject)
    assert subject.shop_url_var.get() == ""
    restarted = SimpleNamespace(config_store=AppConfigStore(config_path), status_var=Status())
    restarted._logo_url = lambda: BookLedgerApp._logo_url(restarted)
    assert restarted._logo_url() == ""
    opened = []
    monkeypatch.setattr(app_module.webbrowser, "open", lambda *args, **kwargs: opened.append((args, kwargs)) or True)
    assert not BookLedgerApp._open_shop_link(restarted)
    assert opened == []


@pytest.mark.parametrize("logo_state", ["missing", "unreadable"])
def test_missing_or_unreadable_custom_logo_falls_back_to_the_bundled_default(tmp_path, monkeypatch, logo_state):
    from bookledger.resources import resource_path

    class LogoLabel:
        def __init__(self):
            self.options = {}
            self.manager = ""

        def configure(self, **options):
            self.options.update(options)

        def pack_forget(self):
            self.manager = ""

        def pack(self, **_options):
            self.manager = "pack"

        def winfo_manager(self):
            return self.manager

    loaded_sizes = []
    monkeypatch.setattr(app_module.ImageTk, "PhotoImage", lambda image, master: loaded_sizes.append(image.size) or object())
    data = tmp_path / "data"
    subject = SimpleNamespace(
        config_store=AppConfigStore(tmp_path / "config.json"),
        paths=SimpleNamespace(data=data),
        brand_logo_label=LogoLabel(),
    )
    if logo_state == "unreadable":
        broken_asset = data / "assets" / "shop-logo-broken.png"
        broken_asset.parent.mkdir(parents=True)
        broken_asset.write_bytes(b"not an image")
        reference = "assets/shop-logo-broken.png"
    else:
        reference = "assets/missing-logo.png"
    subject.config_store.set(("preferences", "shop_logo_path"), reference)

    BookLedgerApp._refresh_brand_logo(subject)

    with Image.open(resource_path("assets", "generalists_bookshop_logo.png")) as default:
        default.thumbnail((176, 66), Image.Resampling.LANCZOS)
        assert loaded_sizes == [default.size]
    assert subject.brand_logo_label.manager == "pack"


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
