from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from PIL import Image, ImageTk

from bookledger.services.posters import POSTER_FIELDS, PosterService, title_for_poster


class PosterDesigner(ttk.Frame):
    """Freeform poster template editor with normalized, portable coordinates."""

    def __init__(self, parent, *, service: PosterService, config_store=None, catalog=None, paths=None):
        super().__init__(parent)
        self.service = service
        self.config_store = config_store
        self.catalog = catalog
        self.paths = paths or service.paths
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
        ttk.Label(toolbar, text="Select Template").pack(side="left", padx=(18, 5))
        self.template_choice = tk.StringVar()
        self.template_combo = ttk.Combobox(toolbar, textvariable=self.template_choice, state="readonly", width=15)
        self.template_combo.pack(side="left")
        self.template_combo.bind("<<ComboboxSelected>>", self._select_template)

        fields = ttk.LabelFrame(self, text="Add field", padding=8)
        fields.grid(row=1, column=0, sticky="nsw", padx=(0, 10))
        for field in POSTER_FIELDS:
            button = ttk.Button(fields, text=field, width=18)
            button.pack(fill="x", pady=2)
            button.bind("<ButtonPress-1>", lambda event, name=field: self._field_press(name, event))
            button.bind("<B1-Motion>", self._field_motion)
            button.bind("<ButtonRelease-1>", self._field_release)
        ttk.Label(fields, text="Drag a field onto the canvas, or click to add it.", wraplength=150).pack(anchor="w", pady=(8, 0))

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
        if not self.catalog:
            messagebox.showerror("Create Poster", "Catalog data is unavailable.", parent=self.winfo_toplevel())
            return
        row = self.catalog.get_copy(int(copy_id))
        template = self.selected_template()
        if row is None:
            messagebox.showerror("Create Poster", "That physical copy could not be found.", parent=self.winfo_toplevel())
            return
        if not template:
            messagebox.showinfo("Create Poster", "Create or select a poster template first in Settings → Poster Setup.", parent=self.winfo_toplevel())
            return
        try:
            # Fail before prompting about replacement if the saved design is broken.
            self.service.resolve_background(template["background_ref"])
            shortened = None
            if len(str(row.get("title") or "").strip()) > 50 and any(el.get("field") == "Title" for el in template["elements"]):
                shortened = simpledialog.askstring("Shorten poster title", "This title exceeds 50 characters. Enter a shorter title for this poster only:", parent=self.winfo_toplevel())
                if shortened is None:
                    self.status.set("Poster creation cancelled.")
                    return
                title_for_poster(row["title"], shortened)
            output = self.paths.posters / f"{row['copy_code']}.png"
            if output.exists() and not messagebox.askyesno("Replace poster", f"{output.name} already exists. Replace it?", parent=self.winfo_toplevel()):
                self.status.set("Poster replacement cancelled; the existing poster was kept.")
                return
            saved = self.service.export(template, row, shortened_title=shortened)
            messagebox.showinfo("Poster created", f"Poster saved to:\n{saved}", parent=self.winfo_toplevel())
            self.status.set(f"Created {saved.name}.")
        except Exception as exc:
            messagebox.showerror("Could not create poster", str(exc), parent=self.winfo_toplevel())
