from types import SimpleNamespace

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
