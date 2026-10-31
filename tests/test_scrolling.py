from types import SimpleNamespace

from bookledger.ui.scrolling import MouseWheelRouter


class _Widget:
    def __init__(self, name, master=None, widget_class="TLabel"):
        self.name = name
        self.master = master
        self.widget_class = widget_class
        self.bindings = {}
        self.calls = []

    def bind_all(self, sequence, callback, add=None):
        self.bindings[sequence] = callback
        return f"{sequence}-id"

    def bind(self, sequence, callback, add=None):
        self.bindings[sequence] = callback
        return f"{sequence}-id"

    def unbind(self, sequence, bind_id=None):
        self.bindings.pop(sequence, None)

    def winfo_containing(self, _x, _y):
        return self.target

    def winfo_class(self):
        return self.widget_class

    def winfo_exists(self):
        return True

    def yview(self):
        return (0.0, 0.5)

    def yview_scroll(self, units, what):
        self.calls.append((units, what))


def _router():
    root = _Widget("root")
    root.target = None
    return root, MouseWheelRouter(root)


def test_wheel_routes_from_nested_content_to_nearest_registered_section():
    root, router = _router()
    outer = _Widget("outer", root)
    inner = _Widget("inner", outer)
    label = _Widget("label", inner)
    outer_scroll = _Widget("outer-scroll")
    inner_scroll = _Widget("inner-scroll")
    router.register(outer_scroll, outer)
    router.register(inner_scroll, inner)
    root.target = label

    result = router._on_mousewheel(SimpleNamespace(widget=label, x_root=5, y_root=6, delta=-120))

    assert result == "break"
    assert inner_scroll.calls == [(1, "units")]
    assert outer_scroll.calls == []


def test_scrollbar_wheel_uses_registered_scroll_widget_and_linux_buttons():
    root, router = _router()
    owner = _Widget("section", root)
    scrollbar = _Widget("scrollbar", owner, "TScrollbar")
    content = _Widget("content")
    router.register(content, owner)
    root.target = scrollbar

    assert router._on_wheel_up(SimpleNamespace(widget=scrollbar, x_root=0, y_root=0)) == "break"
    assert content.calls == [(-1, "units")]


def test_native_entry_and_dropdown_wheel_behavior_is_not_intercepted():
    root, router = _router()
    owner = _Widget("section", root)
    entry = _Widget("entry", owner, "TCombobox")
    scroll = _Widget("scroll")
    router.register(scroll, owner)
    root.target = entry

    result = router._on_mousewheel(SimpleNamespace(widget=entry, x_root=0, y_root=0, delta=-120))

    assert result is None
    assert scroll.calls == []


def test_destroyed_section_is_unregistered_and_no_longer_receives_wheel():
    root, router = _router()
    owner = _Widget("section", root)
    label = _Widget("label", owner)
    scroll = _Widget("scroll")
    router.register(scroll, owner)
    root.target = label

    router._on_owner_destroy(SimpleNamespace(widget=owner))

    assert owner not in router._regions
    assert router._on_mousewheel(SimpleNamespace(widget=label, x_root=0, y_root=0, delta=-120)) is None
    assert scroll.calls == []
