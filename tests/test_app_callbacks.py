from types import SimpleNamespace
from PIL import Image

from bookledger import app as app_module
from bookledger.app import BookLedgerApp


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
