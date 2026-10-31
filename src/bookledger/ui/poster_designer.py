from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from PIL import Image, ImageTk

from bookledger.services.posters import POSTER_FIELDS, PosterService, title_for_poster


def _show_dialog(dialog, title, message, parent):
    try:
        if parent.winfo_exists():
            dialog(title, message, parent=parent)
            return True
    except Exception:
        pass
    return False


def _notify_activity(callback, event, identifier):
    if callback:
        try:
            callback(event, identifier)
        except Exception:
            pass


def create_poster_for_copy(parent, *, service, catalog, paths, config_store, copy_id, on_activity=None):
    """Create a poster through stable application services, independent of page widgets."""
    try:
        row = catalog.get_copy(int(copy_id)) if catalog else None
    except Exception as exc:
        _show_dialog(messagebox.showerror, "Could not create poster", str(exc), parent)
        _notify_activity(on_activity, "poster_generation_failed", int(copy_id))
        return None
    if row is None:
        _show_dialog(messagebox.showerror, "Create Poster", "That physical copy could not be found.", parent)
        return None
    if row.get("status") == "Sold":
        _show_dialog(messagebox.showerror, "Create Poster", "A poster cannot be generated for a Sold copy. Change its status first if the sale was recorded by mistake.", parent)
        return None
    confirmed_not_for_sale = False
    if row.get("status") == "Not for Sale":
        confirmed_not_for_sale = bool(_ask_not_for_sale_confirmation(parent, row))
        if not confirmed_not_for_sale:
            return None
    try:
        templates = service.list_templates()
        template_id = config_store.get(("preferences", "poster_template_id")) if config_store else None
        template = next((item for item in templates if item["id"] == template_id), None)
        template = template or (templates[0] if templates else None)
    except Exception as exc:
        _show_dialog(messagebox.showerror, "Could not create poster", str(exc), parent)
        _notify_activity(on_activity, "poster_generation_failed", int(copy_id))
        return None
    if not template:
        _show_dialog(messagebox.showinfo, "Create Poster", "Create or select a poster template first in Settings → Poster Setup.", parent)
        return None
    try:
        service.resolve_background(template["background_ref"])
        shortened = None
        if len(str(row.get("title") or "").strip()) > 50 and any(el.get("field") == "Title" for el in template["elements"]):
            shortened = simpledialog.askstring(
                "Shorten poster title",
                "This title exceeds 50 characters. Enter a shorter title for this poster only:",
                parent=parent,
            )
            if shortened is None:
                return None
            title_for_poster(row["title"], shortened)
        output = paths.posters / f"{row['copy_code']}.png"
        replacing = output.exists()
        if replacing and not messagebox.askyesno("Replace poster", f"{output.name} already exists. Replace it?", parent=parent):
            return None

        # Modal dialogs run a nested event loop, so validate the canonical
        # physical-copy status again before rendering. A callback captured
        # earlier must not create posters for copies that became Sold.
        current = catalog.get_copy(int(row["copy_id"]))
        if current is None:
            _show_dialog(messagebox.showerror, "Create Poster", "That physical copy could not be found.", parent)
            return None
        if current.get("status") == "Sold":
            _show_dialog(messagebox.showerror, "Create Poster", "A poster cannot be generated for a Sold copy. Change its status first if the sale was recorded by mistake.", parent)
            return None
        if current.get("status") == "Not for Sale" and not confirmed_not_for_sale:
            if not _ask_not_for_sale_confirmation(parent, current):
                return None
            confirmed_not_for_sale = True

        previous_poster = output.read_bytes() if replacing else None
        saved = service.export(template, row, shortened_title=shortened)
        # Export first; only a completed poster may affect inventory status.
        status_changed = False
        try:
            refreshed = catalog.get_copy(int(row["copy_id"]))
            if refreshed is None or refreshed.get("status") == "Sold":
                raise RuntimeError("The copy became Sold while the poster was being created; its status was left unchanged.")
            if refreshed.get("status") in {"Available", "Not for Sale"}:
                catalog.change_status(int(row["copy_id"]), "Listed")
                status_changed = True
        except Exception:
            _restore_poster(output, previous_poster)
            raise
        if status_changed:
            _notify_activity(on_activity, "inventory_status_changed", int(row["copy_id"]))
        _notify_activity(on_activity, "poster_replaced" if replacing else "poster_generated", int(row["copy_id"]))
        _show_dialog(
            messagebox.showinfo,
            "Poster created",
            f"Poster {'replaced' if replacing else 'saved'}:\n{saved.name}\n\nFolder: {saved.parent}",
            parent,
        )
        return saved
    except Exception as exc:
        _notify_activity(on_activity, "poster_generation_failed", int(copy_id))
        _show_dialog(messagebox.showerror, "Could not create poster", str(exc), parent)
        return None


def _ask_not_for_sale_confirmation(parent, row):
    return messagebox.askyesno(
        "List this copy?",
        f"Creating a poster for {row.get('copy_code', 'this copy')} will remove its Not for Sale status and change it to Listed after the poster is created. Continue?",
        parent=parent,
    )


def _restore_poster(output, previous_poster):
    if previous_poster is None:
        output.unlink(missing_ok=True)
    else:
        import os
        import tempfile

        descriptor, temporary = tempfile.mkstemp(prefix=f".{output.stem}-restore-", suffix=".png", dir=output.parent)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(previous_poster)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, output)
        except Exception:
            Path(temporary).unlink(missing_ok=True)
            raise


class PosterDesigner(ttk.Frame):
    """Freeform poster template editor with normalized, portable coordinates."""

    def __init__(self, parent, *, service: PosterService, config_store=None, catalog=None, paths=None, on_open_folder=None, on_activity=None, mousewheel_router=None):
        super().__init__(parent)
        self.service = service
        self.config_store = config_store
        self.catalog = catalog
        self.paths = paths or service.paths
        self._dialog_parent = parent.winfo_toplevel()
        self.on_open_folder = on_open_folder
        self.on_activity = on_activity
        self.mousewheel_router = mousewheel_router
        self.background_ref = ""
        self.background = None
        self.elements: list[dict] = []
        self.selected_index = None
        self._preview_photo = None
        self._scene = (600, 750)
        self._canvas_origin = (0, 0)
        self._drag = None
        self._field_drag = None
        self._build()
        self.reload_templates()

    def _build(self):
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)
        toolbar = ttk.Frame(self, padding=(0, 0, 0, 8))
        toolbar.grid(row=0, column=0, columnspan=3, sticky="ew")
        ttk.Button(toolbar, text="Upload Background", command=self.upload_background).pack(side="left", padx=(0, 6))
        ttk.Button(toolbar, text="Save as New Template", command=self.save_template).pack(side="left", padx=6)
        ttk.Button(toolbar, text="Discard Template", command=self.discard_template).pack(side="left", padx=6)
        if self.on_open_folder:
            ttk.Button(toolbar, text="Open Poster Folder", command=self.on_open_folder).pack(side="left", padx=6)
        ttk.Label(toolbar, text="Select Template").pack(side="left", padx=(18, 5))
        self.template_choice = tk.StringVar()
        self.template_combo = ttk.Combobox(toolbar, textvariable=self.template_choice, state="readonly", width=15)
        self.template_combo.pack(side="left")
        self.template_combo.bind("<<ComboboxSelected>>", self._select_template)

        fields = ttk.LabelFrame(self, text="Add field", padding=4)
        fields.grid(row=1, column=0, sticky="nsw", padx=(0, 10))
        palette_canvas = tk.Canvas(fields, width=178, highlightthickness=0)
        palette_scrollbar = ttk.Scrollbar(fields, orient="vertical", command=palette_canvas.yview)
        palette = ttk.Frame(palette_canvas, padding=4)
        palette_window = palette_canvas.create_window((0, 0), window=palette, anchor="nw")
        palette.bind("<Configure>", lambda _event: palette_canvas.configure(scrollregion=palette_canvas.bbox("all")))
        palette_canvas.bind("<Configure>", lambda event: palette_canvas.itemconfigure(palette_window, width=event.width))
        palette_canvas.configure(yscrollcommand=palette_scrollbar.set)
        palette_canvas.pack(side="left", fill="both", expand=True)
        palette_scrollbar.pack(side="right", fill="y")
        if self.mousewheel_router is not None:
            self.mousewheel_router.register(palette_canvas, fields)
        for field in POSTER_FIELDS:
            button = ttk.Button(palette, text=field, width=18)
            button.pack(fill="x", pady=2)
            button.bind("<ButtonPress-1>", lambda event, name=field: self._field_press(name, event))
            button.bind("<B1-Motion>", self._field_motion)
            button.bind("<ButtonRelease-1>", self._field_release)
        ttk.Label(palette, text="Drag a field onto the canvas, or click to add it.", wraplength=150).pack(anchor="w", pady=(8, 0))

        center = ttk.Frame(self)
        center.grid(row=1, column=1, sticky="nsew")
        center.rowconfigure(0, weight=1)
        center.columnconfigure(0, weight=1)
        self.canvas = tk.Canvas(center, background="#e6eaf0", highlightthickness=0, width=600, height=640)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.canvas.bind("<Configure>", self._draw_scene)
        self.canvas.bind("<ButtonPress-1>", self._mouse_down)
        self.canvas.bind("<B1-Motion>", self._mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self._mouse_up)

        tools = ttk.LabelFrame(self, text="Selected element", padding=8)
        tools.grid(row=1, column=2, sticky="nse", padx=(10, 0))
        ttk.Label(tools, text="Font size").pack(anchor="w")
        self.font_size = tk.StringVar(value="28")
        self.font_spin = ttk.Spinbox(tools, from_=8, to=160, textvariable=self.font_size, width=8, command=self._font_changed)
        self.font_spin.pack(anchor="w", pady=(2, 8))
        self.font_spin.bind("<Return>", lambda _event: self._font_changed())
        self.font_spin.bind("<FocusOut>", lambda _event: self._font_changed())
        ttk.Button(tools, text="Remove element", command=self.remove_selected).pack(fill="x")
        ttk.Label(tools, text="Drag a field to move it.\nDrag its lower-right handle to resize it.", wraplength=150).pack(anchor="w", pady=(10, 0))
        self.status = tk.StringVar(value="Choose a background to begin.")
        ttk.Label(self, textvariable=self.status, wraplength=740).grid(row=2, column=0, columnspan=3, sticky="ew", pady=(8, 0))

    def reload_templates(self, prefer_id=None):
        self.templates = self.service.list_templates()
        self._template_by_label = {row["name"]: row for row in self.templates}
        labels = [row["name"] for row in self.templates]
        self.template_combo.configure(values=labels)
        selected = next((row for row in self.templates if row["id"] == prefer_id), None)
        saved_id = None
        if self.config_store:
            try:
                saved_id = self.config_store.get(("preferences", "poster_template_id"))
            except Exception:
                saved_id = None
        selected = selected or next((row for row in self.templates if row["id"] == saved_id), None)
        if selected:
            self.template_choice.set(selected["name"])
            self._load_template(selected)
        elif labels:
            self.template_choice.set(labels[0])
            self._load_template(self._template_by_label[labels[0]])
        else:
            self.template_choice.set("")
            self.background_ref = ""
            self.background = None
            self.elements = []
            self._draw_scene()

    def selected_template(self):
        label = self.template_choice.get()
        return self._template_by_label.get(label)

    def _select_template(self, _event=None):
        row = self.selected_template()
        if row:
            self._load_template(row)

    def _load_template(self, row):
        try:
            path = self.service.resolve_background(row["background_ref"])
            with Image.open(path) as image:
                image.load()
                self.background = image.copy()
            self.background_ref = row["background_ref"]
            self.elements = [dict(item) for item in row["elements"]]
            self.selected_index = None
            self.status.set(
                f"Loaded {row['name']} with an invalid saved layout cleared."
                if row.get("invalid_elements") else f"Loaded {row['name']}."
            )
            self._draw_scene()
            if self.config_store:
                self.config_store.set(("preferences", "poster_template_id"), row["id"])
        except Exception as exc:
            self.background = None
            self.status.set(f"Could not load {row['name']}: {exc}")

    def upload_background(self):
        source = filedialog.askopenfilename(parent=self.winfo_toplevel(), title="Choose poster background", filetypes=[("Images", "*.png *.jpg *.jpeg *.webp"), ("All files", "*.*")])
        if not source:
            return
        try:
            self.background_ref, path = self.service.add_background(source)
            with Image.open(path) as image:
                image.load()
                self.background = image.copy()
            self.elements = []
            self.selected_index = None
            self.template_choice.set("")
            self.status.set("Background loaded. Add fields, then save it as a new template.")
            self._draw_scene()
        except Exception as exc:
            messagebox.showerror("Background unavailable", str(exc), parent=self.winfo_toplevel())

    def save_template(self):
        if not self.background_ref:
            messagebox.showinfo("Poster template", "Upload a background before saving a template.", parent=self.winfo_toplevel())
            return
        try:
            row = self.service.save_template(self.background_ref, self.elements)
            _notify_activity(self.on_activity, "poster_template_saved", row.get("id"))
            self.reload_templates(row["id"])
            self.status.set(f"Saved {row['name']}.")
        except Exception as exc:
            messagebox.showerror("Could not save template", str(exc), parent=self.winfo_toplevel())

    def discard_template(self):
        row = self.selected_template()
        if not row:
            self.status.set("Select a saved template to discard.")
            return
        if not messagebox.askyesno("Discard template", f"Delete {row['name']}? This cannot be undone.", parent=self.winfo_toplevel()):
            return
        self.service.discard_template(row["id"])
        _notify_activity(self.on_activity, "poster_template_discarded", row.get("id"))
        self.reload_templates()
        self.status.set(f"Discarded {row['name']}.")

    def add_element(self, field):
        if not self.background_ref:
            self.status.set("Upload a background before adding fields.")
            return
        self._append_element(field)

    def _append_element(self, field, at=None):
        item = {"field": field, "type": "image" if field == "Photo" else "text", "x": 0.08, "y": 0.08 + (len(self.elements) % 8) * 0.085, "w": 0.48 if field != "Photo" else 0.34, "h": 0.10 if field != "Photo" else 0.28, "font_size": 28, "font_family": "Arial"}
        if at:
            item["x"] = max(0, min(1 - item["w"], at[0]))
            item["y"] = max(0, min(1 - item["h"], at[1]))
        self.elements.append(item)
        self.selected_index = len(self.elements) - 1
        self.font_size.set(str(item["font_size"]))
        self._draw_scene()

    def _field_press(self, field, _event):
        self._field_drag = field

    def _field_motion(self, _event):
        return "break"

    def _field_release(self, event):
        field = self._field_drag
        self._field_drag = None
        if not field:
            return "break"
        left, top = self.canvas.winfo_rootx(), self.canvas.winfo_rooty()
        x, y = event.x_root - left, event.y_root - top
        inside = 0 <= x <= self.canvas.winfo_width() and 0 <= y <= self.canvas.winfo_height()
        if inside and self.background_ref:
            self._append_element(field, self._scene_point(self.canvas.canvasx(x), self.canvas.canvasy(y)))
        else:
            self.add_element(field)
        return "break"

    def _scene_geometry(self, canvas_width=None, canvas_height=None):
        if self.background is None:
            scene_w, scene_h = 600, 750
        else:
            scene_w, scene_h = self.background.size
        canvas_width = canvas_width or self.canvas.winfo_width()
        canvas_height = canvas_height or self.canvas.winfo_height()
        if canvas_width <= 1:
            canvas_width = 620
        if canvas_height <= 1:
            canvas_height = 650
        scale = min(600 / scene_w, 620 / scene_h, max(100, canvas_width - 20) / scene_w, max(100, canvas_height - 20) / scene_h, 1)
        preview = (max(1, round(scene_w * scale)), max(1, round(scene_h * scale)))
        return (scene_w, scene_h), preview, (max(0, (canvas_width - preview[0]) // 2), max(0, (canvas_height - preview[1]) // 2))

    def _draw_scene(self, _event=None):
        if not hasattr(self, "canvas"):
            return
        (scene_w, scene_h), (view_w, view_h), (origin_x, origin_y) = self._scene_geometry()
        self._scene = (scene_w, scene_h)
        self._canvas_origin = (origin_x, origin_y)
        self.canvas.delete("all")
        if self.background is None:
            self.canvas.create_rectangle(origin_x, origin_y, origin_x + view_w, origin_y + view_h, fill="#ffffff", outline="#9ca3af", width=1)
            self.canvas.create_text(origin_x + view_w / 2, origin_y + view_h / 2, text="Poster canvas", fill="#94a3b8", font=("Segoe UI", 16))
            return
        preview = self.background.copy()
        preview.thumbnail((view_w, view_h), Image.Resampling.LANCZOS)
        self._preview_photo = ImageTk.PhotoImage(preview)
        view_w, view_h = preview.size
        self._canvas_origin = (origin_x, origin_y)
        self.canvas.create_image(origin_x, origin_y, image=self._preview_photo, anchor="nw", tags=("scene",))
        for index, item in enumerate(self.elements):
            x, y = origin_x + float(item["x"]) * view_w, origin_y + float(item["y"]) * view_h
            w, h = float(item["w"]) * view_w, float(item["h"]) * view_h
            selected = index == self.selected_index
            color = "#166534" if selected else "#111827"
            size = max(8, round(float(item.get("font_size", 28)) * view_w / 600))
            if item["field"] == "Photo":
                self.canvas.create_rectangle(x, y, x + w, y + h, outline=color, width=2 if selected else 1, dash=(4, 3), tags=(f"element-{index}",))
                self.canvas.create_text(x + w / 2, y + h / 2, text="Photo", fill=color, font=("Segoe UI", size), tags=(f"element-{index}",))
            else:
                title = item["field"]
                self.canvas.create_rectangle(x, y, x + w, y + h, outline=color if selected else "", width=2, tags=(f"element-{index}",))
                self.canvas.create_text(x, y, text=title, anchor="nw", width=max(20, w), fill=color, font=("Arial", size), tags=(f"element-{index}",))
            if selected:
                self.canvas.create_rectangle(x + w - 5, y + h - 5, x + w + 5, y + h + 5, fill="#166534", outline="white", tags=("resize-handle",))

    def _scene_point(self, x, y):
        (scene_w, scene_h), (view_w, view_h), (origin_x, origin_y) = self._scene_geometry()
        return (x - origin_x) / max(1, view_w), (y - origin_y) / max(1, view_h)

    def _mouse_down(self, event):
        if not self.elements:
            return
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        if self.canvas.find_withtag("current") and "resize-handle" in self.canvas.gettags("current") and self.selected_index is not None:
            item = self.elements[self.selected_index]
            self._drag = ("resize", self.selected_index, x, y, item["w"], item["h"])
            return
        index = next((i for i in range(len(self.elements) - 1, -1, -1) if self.canvas.find_withtag(f"element-{i}") and self.canvas.bbox(f"element-{i}") and self._inside(self.canvas.bbox(f"element-{i}"), x, y)), None)
        if index is None:
            self.selected_index = None
            self._draw_scene()
            return
        self.selected_index = index
        item = self.elements[index]
        self.font_size.set(str(item.get("font_size", 28)))
        nx, ny = self._scene_point(x, y)
        self._drag = ("move", index, nx - item["x"], ny - item["y"])
        self._draw_scene()

    @staticmethod
    def _inside(box, x, y):
        return box[0] <= x <= box[2] and box[1] <= y <= box[3]

    def _mouse_drag(self, event):
        if not self._drag:
            return
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        kind, index = self._drag[:2]
        item = self.elements[index]
        if kind == "move":
            nx, ny = self._scene_point(x, y)
            item["x"] = max(0, min(0.98, nx - self._drag[2]))
            item["y"] = max(0, min(0.98, ny - self._drag[3]))
        else:
            _, _, start_x, start_y, start_w, start_h = self._drag
            _scene, (view_w, view_h), _origin = self._scene_geometry()
            item["w"] = max(0.05, min(1 - item["x"], start_w + (x - start_x) / view_w))
            item["h"] = max(0.05, min(1 - item["y"], start_h + (y - start_y) / view_h))
        self._draw_scene()

    def _mouse_up(self, _event):
        self._drag = None

    def _font_changed(self):
        if self.selected_index is None:
            return
        try:
            size = max(8, min(160, int(self.font_size.get())))
        except ValueError:
            return
        self.elements[self.selected_index]["font_size"] = size
        self._draw_scene()

    def remove_selected(self):
        if self.selected_index is not None:
            del self.elements[self.selected_index]
            self.selected_index = None
            self._draw_scene()

    def create_poster(self, copy_id: int):
        saved = create_poster_for_copy(
            self._dialog_parent,
            service=self.service,
            catalog=self.catalog,
            paths=self.paths,
            config_store=self.config_store,
            copy_id=copy_id,
            on_activity=self.on_activity,
        )
        if saved:
            try:
                self.status.set(f"Created {saved.name}.")
            except tk.TclError:
                pass

    @staticmethod
    def _show_dialog(dialog, title, message, *, parent):
        return _show_dialog(dialog, title, message, parent)
