"""Route mouse-wheel input to the scrollable section under the pointer."""

from __future__ import annotations

import sys


class MouseWheelRouter:
    """Install one Tk-level wheel binding and route it to registered sections.

    A section is represented by a scrollable widget and an owner frame. Looking
    up the nearest owner from the pointer widget keeps nested sections isolated
    and lets registrations disappear when their view is destroyed.
    """

    _NATIVE_WHEEL_CONTROLS = {
        "entry", "tentry", "combobox", "tcombobox", "spinbox", "tspinbox",
        "listbox", "treeview", "text",
    }

    def __init__(self, root):
        self.root = root
        self._regions = {}
        self._fractions = {}
        root.bind_all("<MouseWheel>", self._on_mousewheel, add="+")
        root.bind_all("<Button-4>", self._on_wheel_up, add="+")
        root.bind_all("<Button-5>", self._on_wheel_down, add="+")

    def register(self, scroll_widget, owner):
        """Register a scroll widget for pointer events inside ``owner``."""
        self.unregister(owner)
        try:
            binding = owner.bind("<Destroy>", self._on_owner_destroy, add="+")
        except Exception:
            binding = None
        self._regions[owner] = (scroll_widget, binding)
        return owner

    def unregister(self, owner):
        record = self._regions.pop(owner, None)
        self._fractions.pop(owner, None)
        if record and record[1]:
            try:
                owner.unbind("<Destroy>", record[1])
            except Exception:
                pass

    def _on_owner_destroy(self, event):
        owner = event.widget
        if owner in self._regions:
            self.unregister(owner)

    @staticmethod
    def _widget_chain(widget):
        while widget is not None:
            yield widget
            widget = getattr(widget, "master", None)

    def _region_under_pointer(self, event):
        try:
            target = self.root.winfo_containing(event.x_root, event.y_root)
        except Exception:
            target = None
        target = target or getattr(event, "widget", None)
        for widget in self._widget_chain(target):
            record = self._regions.get(widget)
            if record:
                return widget, record[0]
        return None, None

    def _dispatch(self, event, units):
        target = getattr(event, "widget", None)
        try:
            target = self.root.winfo_containing(event.x_root, event.y_root) or target
        except Exception:
            pass
        try:
            if self._is_native_wheel_control(target):
                return None
        except Exception:
            pass
        owner, scroll_widget = self._region_under_pointer(event)
        if owner is None:
            return None
        try:
            if not scroll_widget.winfo_exists():
                self.unregister(owner)
                return None
            first, last = scroll_widget.yview()
            if float(first) <= 0 and float(last) >= 1:
                return "break"
            scroll_widget.yview_scroll(units, "units")
            return "break"
        except Exception:
            self.unregister(owner)
            return None

    def _on_mousewheel(self, event):
        target = getattr(event, "widget", None)
        try:
            target = self.root.winfo_containing(event.x_root, event.y_root) or target
        except Exception:
            pass
        if self._is_native_wheel_control(target):
            return None
        owner, _scroll_widget = self._region_under_pointer(event)
        if owner is None:
            return None
        if sys.platform == "darwin":
            units = -float(getattr(event, "delta", 0))
        else:
            delta = -float(getattr(event, "delta", 0)) / 120.0
            delta += self._fractions.get(owner, 0.0)
            units = int(delta)
            self._fractions[owner] = delta - units
        if units == 0:
            # Keep high-resolution touchpad motion for the next wheel event.
            return "break"
        return self._dispatch(event, units)

    def _on_wheel_up(self, event):
        return self._dispatch(event, -1)

    def _on_wheel_down(self, event):
        return self._dispatch(event, 1)

    @classmethod
    def _is_native_wheel_control(cls, widget):
        try:
            return str(widget.winfo_class()).casefold() in cls._NATIVE_WHEEL_CONTROLS
        except Exception:
            return False
