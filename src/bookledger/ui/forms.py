from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from queue import Empty, SimpleQueue
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from bookledger.config import APPROVED_GENRES, BOOK_CONDITIONS, DEFAULT_FORMATS, DEFAULT_LOCATION
from bookledger.services.catalog import CatalogService, ValidationError
from bookledger.services.isbn import normalize_isbn
from bookledger.provider_registry import PROVIDERS_BY_NAME
from bookledger.services.metadata import MetadataLookupService, MetadataResult
from bookledger.resources import apply_application_icon
from bookledger.ui.status_colors import status_message_color

NO_DATA = "No Data"
OPTIONAL_METADATA_FIELDS = frozenset({"publisher", "publication_year", "edition", "page_count", "srp", "book_details"})


class BookForm(tk.Toplevel):
    """Add/edit form for catalog records and individual physical copies."""

    def __init__(
        self,
        parent,
        *,
        service: CatalogService,
        photo_service,
        on_saved,
        on_activity=None,
        mousewheel_router=None,
        existing=None,
        existing_book_id=None,
        metadata_lookup: MetadataLookupService | None = None,
        initial_isbn=None,
        initial_photo=None,
        incoming_capture_id=None,
        on_discard_incoming=None,
        on_cancel=None,
    ):
        super().__init__(parent)
        apply_application_icon(self)
        self.parent = parent
        self.service = service
        self.photo_service = photo_service
        self.on_saved = on_saved
        self.on_activity = on_activity
        self.mousewheel_router = mousewheel_router
        self.existing = existing
        self.existing_book_id = existing_book_id
        self.incoming_capture_id = incoming_capture_id
        self.on_discard_incoming = on_discard_incoming
        self.on_cancel = on_cancel
        self._incoming_sequence_finished = False
        self.incoming_copy_uuid = incoming_capture_id
        self.metadata_lookup = metadata_lookup or MetadataLookupService()
        self.photo_path = tk.StringVar(value="")
        self.isbn_override = tk.BooleanVar(value=False)
        self.metadata_status = tk.StringVar(value="Manual entry")
        self.metadata_source = (existing or {}).get("metadata_source")
        self.provider_status_vars = {}
        self.provider_status_labels = {}
        self._provider_status_widgets = []
        self._provider_names = []
        self._widgets = {}
        self._errors = {}
        self._field_labels = {}
        self._active_operation = None
        self._operation_serial = 0
        self._photo_image = None
        self._photo_source = None
        self._photo_fit_bounds = None
        self._ui_queue = SimpleQueue()
        self._ui_poll_id = None
        self._closing = False

        self.title("Edit Book" if existing else "Add Book")
        self.geometry("1120x700")
        self.minsize(960, 700)
        self.transient(parent)
        self.grab_set()
        self._build()
        for key in OPTIONAL_METADATA_FIELDS:
            self._set(key, None)
        if existing:
            self._populate(existing)
        else:
            self._set("location", DEFAULT_LOCATION)
            if initial_isbn:
                self._set("isbn", initial_isbn)
            if initial_photo:
                self.set_photo(initial_photo)
            if incoming_capture_id:
                ttk.Button(
                    self.actions_panel,
                    text="Discard Incoming Capture",
                    command=self._discard_incoming,
                ).grid(row=1, column=0, columnspan=4, sticky="ew", pady=(8, 0))
        self.update_idletasks()
        # The canvas does not propagate the scrollable body's requested height.
        content_height = max(self.body.winfo_reqheight(), self.right_panel.winfo_reqheight())
        self.geometry(f"1120x{max(700, content_height + 28)}")
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.bind("<Destroy>", self._on_destroy, add="+")
        self._ui_poll_id = self.after(40, self._poll_ui_queue)

    def _build(self):
        outer = ttk.Frame(self, padding=14)
        outer.grid(row=0, column=0, sticky="nsew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(0, weight=1)

        content = ttk.Frame(outer)
        content.grid(row=0, column=0, sticky="nsew")
        content.columnconfigure(0, weight=3, minsize=500)
        content.columnconfigure(1, weight=2, minsize=300)
        content.rowconfigure(0, weight=1)

        form_side = ttk.Frame(content)
        form_side.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        form_side.columnconfigure(0, weight=1)
        form_side.rowconfigure(0, weight=1)
        canvas = tk.Canvas(form_side, highlightthickness=0)
        scrollbar = ttk.Scrollbar(form_side, orient="vertical", command=canvas.yview)
        body = ttk.Frame(canvas)
        body.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        self._form_canvas_window = canvas.create_window((0, 0), window=body, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        if self.mousewheel_router is not None:
            self.mousewheel_router.register(canvas, form_side)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(self._form_canvas_window, width=event.width))
        self.body = body
        body.columnconfigure(0, weight=0, uniform="form-labels")
        body.columnconfigure(1, weight=1, uniform="form-inputs")
        body.columnconfigure(2, weight=0, uniform="form-labels")
        body.columnconfigure(3, weight=1, uniform="form-inputs")

        row = 0
        ttk.Label(body, text="Bibliographic Details", font=("Segoe UI", 12, "bold")).grid(row=row, column=0, columnspan=4, sticky="w", pady=(0, 8))
        row += 1
        row = self._field(body, "Title", "title", row, required=True, full_width=True)
        row = self._field(body, "Author", "author", row, required=True, full_width=True)
        row = self._field(body, "ISBN (Optional)", "isbn", row, full_width=True)
        self.isbn_controls = ttk.Frame(body)
        self.isbn_controls.grid(row=row, column=1, columnspan=3, sticky="w", pady=(0, 6))
        row += 1
        self.lookup_button = ttk.Button(self.isbn_controls, text="Look Up ISBN", command=self._lookup_metadata)
        self.lookup_button.pack(side="left")
        ttk.Checkbutton(
            self.isbn_controls,
            text="Override ISBN Validation",
            variable=self.isbn_override,
        ).pack(side="left", padx=(10, 0))
        genre_values = self.service.list_genres() if hasattr(self.service, "list_genres") else APPROVED_GENRES
        format_values = self.service.list_formats() if hasattr(self.service, "list_formats") else DEFAULT_FORMATS
        for left, right in (
            (("Genre", "genre", {"required": True, "values": genre_values}), ("Edition", "edition", {})),
            (("Publisher/Imprint", "publisher", {}), ("Page Count", "page_count", {})),
            (("Publication Year", "publication_year", {}), ("SRP", "srp", {"read_only": True})),
        ):
            self._field(body, left[0], left[1], row, column=0, **left[2])
            self._field(body, right[0], right[1], row, column=2, **right[2])
            row += 2
        row = self._multiline_field(body, "Book Details/Synopsis", "book_details", row)

        ttk.Label(body, text="Physical Copy", font=("Segoe UI", 12, "bold")).grid(row=row, column=0, columnspan=4, sticky="w", pady=(18, 8))
        row += 1
        self._field(body, "Format", "format", row, column=0, required=True, values=format_values)
        self._field(body, "Location", "location", row, column=2, values=self.service.list_locations())
        row += 2
        self._field(body, "Condition", "condition", row, column=0, required=True, values=BOOK_CONDITIONS)
        self._field(body, "Price (PHP)", "price", row, column=2, required=True)
        row += 2
        row = self._photo_row(body, row)

        self.error_summary = ttk.Label(body, text="", foreground="#b42318", wraplength=620)
        self.error_summary.grid(row=row, column=0, columnspan=4, sticky="w", pady=(6, 0))
        self._build_actions(body, row + 1)

        self.right_panel = ttk.Frame(content)
        self.right_panel.grid(row=0, column=1, sticky="nsew")
        self.right_panel.columnconfigure(0, weight=1)
        self.right_panel.rowconfigure(0, weight=1)
        self.photo_panel = ttk.LabelFrame(self.right_panel, text="Photo Preview", padding=12)
        self.photo_panel.grid(row=0, column=0, sticky="nsew")
        self.photo_preview = tk.Label(
            self.photo_panel,
            text="No Photo Selected",
            width=30,
            height=20,
            relief="groove",
            borderwidth=2,
            compound="center",
            wraplength=200,
        )
        self.photo_preview.pack(fill="both", expand=True)
        self.photo_preview.bind("<Configure>", self._fit_photo_preview)
        self._build_metadata_status_panel(self.right_panel)
        self._bind_status_color(self.metadata_status, self.metadata_label)
        self._update_control_states()

    @staticmethod
    def _bind_status_color(variable, label):
        def update_color(*_args):
            label.configure(foreground=status_message_color(variable.get()))

        variable.trace_add("write", update_color)
        update_color()

    def _field(self, parent, label, key, row, *, required=False, values=None, read_only=False, column=0, full_width=False):
        if full_width:
            field_parent = parent
            label_column, label_span = 0, 1
            widget_column, widget_span = 1, 3
            label_row = widget_row = row
            error_row, next_row = row + 1, row + 2
        else:
            field_parent = parent
            label_column, label_span = column, 1
            widget_column, widget_span = column + 1, 1
            label_row = widget_row = row
            error_row, next_row = row + 1, row + 2
        field_label = ttk.Label(field_parent, text=f"{label} *" if required else label)
        label_padx = (16, 8) if column == 2 and not full_width else (0, 8)
        field_label.grid(row=label_row, column=label_column, columnspan=label_span, sticky="w", padx=label_padx, pady=4)
        self._field_labels[key] = field_label
        if values:
            widget = ttk.Combobox(field_parent, values=values, width=14 if not full_width else 32)
            if key != "genre":
                widget.configure(state="readonly")
        else:
            widget = ttk.Entry(field_parent, width=12 if not full_width else 34)
            if read_only:
                widget.configure(state="readonly")
        widget.grid(row=widget_row, column=widget_column, columnspan=widget_span, sticky="ew", pady=4)
        self._widgets[key] = widget
        error = ttk.Label(field_parent, text="", foreground="#b42318", wraplength=560 if full_width else 1)
        error.grid(row=error_row, column=widget_column, columnspan=widget_span, sticky="ew", pady=(0, 3))
        self._errors[key] = error
        if not full_width:
            error.bind(
                "<Configure>",
                lambda event, target=error: target.configure(wraplength=max(1, event.width))
                if int(target.cget("wraplength")) != event.width
                else None,
                add="+",
            )
        widget.bind("<KeyRelease>", lambda _event, field=key: self._clear_valid_error(field), add="+")
        if key == "isbn":
            widget.bind("<KeyRelease>", lambda _event: self._isbn_changed(), add="+")
        if key in OPTIONAL_METADATA_FIELDS and key != "srp":
            widget.bind("<FocusIn>", lambda _event, field=key: self._clear_placeholder(field), add="+")
            widget.bind("<FocusOut>", lambda _event, field=key: self._restore_placeholder(field), add="+")
        if isinstance(widget, ttk.Combobox):
            widget.bind("<<ComboboxSelected>>", lambda _event, field=key: self._clear_valid_error(field), add="+")
        return next_row

    def _multiline_field(self, parent, label, key, row):
        field_label = ttk.Label(parent, text=label)
        field_label.grid(row=row, column=0, sticky="nw", padx=(0, 10), pady=4)
        widget = tk.Text(parent, height=3, width=34, wrap="word", relief="solid", borderwidth=1)
        widget.grid(row=row, column=1, columnspan=3, sticky="ew", pady=4)
        self._widgets[key] = widget
        error = ttk.Label(parent, text="", foreground="#b42318", wraplength=560)
        error.grid(row=row + 1, column=1, columnspan=3, sticky="w", pady=(0, 3))
        self._errors[key] = error
        self._field_labels[key] = field_label
        widget.bind("<KeyRelease>", lambda _event: self._clear_valid_error(key), add="+")
        if key in OPTIONAL_METADATA_FIELDS:
            widget.bind("<FocusIn>", lambda _event, field=key: self._clear_placeholder(field), add="+")
            widget.bind("<FocusOut>", lambda _event, field=key: self._restore_placeholder(field), add="+")
        return row + 2

    def _photo_row(self, parent, row):
        photo_label = ttk.Label(parent, text="Copy Photo *")
        photo_label.grid(row=row, column=0, sticky="w", padx=(0, 10), pady=4)
        self._field_labels["photo_path"] = photo_label
        controls = ttk.Frame(parent)
        controls.grid(row=row, column=1, columnspan=3, sticky="ew", pady=4)
        self.photo_path_label = ttk.Label(controls, text="No Photo Selected", width=25)
        self.photo_path_label.pack(side="left", fill="x", expand=True)
        ttk.Button(controls, text="Choose Photo", command=self._choose_photo).pack(side="left", padx=(8, 0))
        self._errors["photo_path"] = ttk.Label(parent, text="", foreground="#b42318", wraplength=560)
        self._errors["photo_path"].grid(row=row + 1, column=1, columnspan=3, sticky="w", pady=(0, 3))
        return row + 2

    def _build_metadata_status_panel(self, parent):
        panel = ttk.LabelFrame(parent, text="Metadata Status", padding=(10, 8))
        self.metadata_status_panel = panel
        panel.grid(row=1, column=0, sticky="ew", pady=(10, 8))
        panel.columnconfigure(1, weight=1)
        self.metadata_label = ttk.Label(panel, textvariable=self.metadata_status, foreground="#334155", wraplength=360)
        self.metadata_label.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))
        self._sync_provider_statuses()

    def _sync_provider_statuses(self):
        names = []
        for provider in getattr(self.metadata_lookup, "providers", ()):
            if provider.name in PROVIDERS_BY_NAME and provider.name not in names:
                names.append(provider.name)
        if names == self._provider_names:
            return
        old_vars = self.provider_status_vars
        for widget in self._provider_status_widgets:
            widget.destroy()
        self._provider_status_widgets = []
        self.provider_status_labels = {}
        self.provider_status_vars = {}
        self._provider_names = names
        for row, name in enumerate(names, start=1):
            variable = old_vars.get(name, tk.StringVar(value="Not attempted"))
            self.provider_status_vars[name] = variable
            name_label = ttk.Label(self.metadata_status_panel, text=f"{name}:", foreground="#596579")
            status_label = ttk.Label(self.metadata_status_panel, textvariable=variable, foreground="#596579", wraplength=360)
            name_label.grid(row=row, column=0, sticky="nw", padx=(0, 6))
            status_label.grid(row=row, column=1, sticky="nw")
            self._provider_status_widgets.extend((name_label, status_label))
            self.provider_status_labels[name] = status_label

    def _set_provider_status(self, name, status):
        variable = self.provider_status_vars.get(name)
        if variable is not None:
            variable.set(status)
            self.provider_status_labels[name].configure(foreground=status_message_color(status))

    def _build_actions(self, parent, row):
        actions = ttk.Frame(parent)
        self.actions_panel = actions
        actions.grid(row=row, column=0, columnspan=4, sticky="ew", pady=(8, 0))
        for column in range(4):
            actions.columnconfigure(column, weight=1, uniform="form-actions")
        self.save_button = ttk.Button(actions, text="Save Book", command=self._save)
        self.refresh_button = ttk.Button(actions, text="Refresh", command=self._refresh)
        self.clear_button = ttk.Button(actions, text="Clear", command=self._clear)
        self.cancel_button = ttk.Button(actions, text="Cancel", command=self._close)
        for column, button in enumerate((self.save_button, self.refresh_button, self.clear_button, self.cancel_button)):
            button.grid(row=0, column=column, sticky="ew", padx=(0, 8) if column < 3 else 0)

    def _set(self, key, value):
        widget = self._widgets.get(key)
        if widget is None:
            return
        display_value = NO_DATA if key in OPTIONAL_METADATA_FIELDS and value in (None, "") else ("" if value is None else str(value))
        if isinstance(widget, tk.Text):
            widget.delete("1.0", "end")
            widget.insert("1.0", display_value)
        else:
            prior_state = str(widget.cget("state"))
            widget.configure(state="normal")
            widget.delete(0, "end")
            widget.insert(0, display_value)
            if key == "srp" or (isinstance(widget, ttk.Combobox) and key != "genre") or prior_state == "readonly":
                widget.configure(state="readonly")

    def _get(self, key):
        widget = self._widgets[key]
        if isinstance(widget, tk.Text):
            value = widget.get("1.0", "end-1c").strip()
        else:
            value = widget.get().strip()
        return "" if key in OPTIONAL_METADATA_FIELDS and value == NO_DATA else value

    def _clear_placeholder(self, key):
        widget = self._widgets.get(key)
        if widget is None or key == "srp":
            return
        if isinstance(widget, tk.Text):
            if widget.get("1.0", "end-1c").strip() == NO_DATA:
                widget.delete("1.0", "end")
        elif widget.get().strip() == NO_DATA:
            widget.delete(0, "end")

    def _restore_placeholder(self, key):
        if key in OPTIONAL_METADATA_FIELDS and key != "srp" and not self._get(key):
            self._set(key, None)

    def _populate(self, row):
        for key in ("title", "author", "isbn", "genre", "publisher", "publication_year", "edition", "page_count", "book_details", "format", "condition", "location"):
            if key in self._widgets:
                self._set(key, row.get(key))
        price_minor = row.get("price_minor")
        self._set("price", f"{price_minor / 100:.2f}" if price_minor is not None else "")
        if row.get("status") == "Sold":
            self._widgets["price"].configure(state="disabled")
            self._errors["price"].configure(text="Price is locked while Sold. Change the status before editing Price.", foreground="#596579")
        if "srp" in self._widgets:
            self._set("srp", f"{row['srp_minor'] / 100:.2f}" if row.get("srp_minor") is not None else "")
        if row.get("photo_path"):
            self.set_photo(row["photo_path"])

    def _resolve_photo(self, value: str | Path) -> Path:
        path = Path(value)
        return path if path.is_absolute() else self.service.data_dir / path

    def set_photo(self, value: str | Path):
        """Display a selected or staged photo in the form."""
        self.photo_path.set(str(value))
        self.photo_path_label.configure(text=Path(value).name or str(value))
        try:
            with Image.open(self._resolve_photo(value)) as source:
                self._photo_source = source.convert("RGB")
            self._photo_fit_bounds = None
            self._fit_photo_preview()
        except (OSError, tk.TclError):
            self._photo_source = None
            self._photo_image = None
            self._photo_fit_bounds = None
            self.photo_preview.configure(image="", text="Photo Preview Unavailable")
        self._clear_valid_error("photo_path")

    def _fit_photo_preview(self, _event=None):
        if self._photo_source is None:
            return
        width, height = self.photo_preview.winfo_width() - 4, self.photo_preview.winfo_height() - 4
        if width < 2 or height < 2:
            width, height = 240, 320
        bounds = (width, height)
        if bounds == self._photo_fit_bounds:
            return
        image = self._photo_source.copy()
        image.thumbnail(bounds, Image.Resampling.LANCZOS)
        self._photo_fit_bounds = bounds
        self._photo_image = ImageTk.PhotoImage(image)
        self.photo_preview.configure(image=self._photo_image, text="")

    def _replace_staged_photo(self, new_path):
        previous = self.photo_path.get()
        if previous and Path(previous) != Path(new_path):
            self.photo_service.discard_staged(previous)

    def _choose_photo(self):
        path = filedialog.askopenfilename(
            parent=self,
            title="Choose a Book Photo",
            filetypes=[("Images", "*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            compressed = self.photo_service.import_and_compress(path)
            self._replace_staged_photo(compressed)
            self.set_photo(compressed)
        except ValueError as exc:
            current = {key: label.cget("text") for key, label in self._errors.items() if label.cget("text")}
            current["photo_path"] = str(exc)
            self._populate_validation(current)

    def _schedule_ui(self, callback):
        self._ui_queue.put(callback)

    def _poll_ui_queue(self):
        self._ui_poll_id = None
        if self._closing:
            return
        while True:
            try:
                callback = self._ui_queue.get_nowait()
            except Empty:
                break
            callback()
        try:
            self._ui_poll_id = self.after(40, self._poll_ui_queue)
        except tk.TclError:
            self._closing = True

    def _on_destroy(self, event):
        if event.widget is self:
            self._closing = True
            if self._ui_poll_id:
                try:
                    self.after_cancel(self._ui_poll_id)
                except tk.TclError:
                    pass
                self._ui_poll_id = None

    def _discard_incoming(self):
        if not self.incoming_capture_id or not self.on_discard_incoming:
            return
        if not messagebox.askyesno(
            "Discard Incoming Capture",
            "Permanently discard this received book and its staged photograph?",
            parent=self,
        ):
            return
        try:
            if self.on_discard_incoming(self.incoming_capture_id):
                self._incoming_sequence_finished = True
                self._close()
        except Exception as exc:
            messagebox.showerror(
                "Could Not Discard Capture",
                f"The incoming capture was retained. ({type(exc).__name__})",
                parent=self,
            )

    def _close(self):
        if self.incoming_capture_id and not self._incoming_sequence_finished:
            if not messagebox.askyesno(
                "Cancel Incoming Capture",
                "Discard this incoming capture and its staged photo? Other captures will be kept.",
                parent=self,
            ):
                return
            try:
                if self.on_cancel and self.on_cancel(self.incoming_capture_id) is False:
                    raise RuntimeError("The incoming capture could not be discarded.")
                self._incoming_sequence_finished = True
            except Exception as exc:
                messagebox.showerror(
                    "Could Not Cancel Capture",
                    f"The incoming capture was retained. ({type(exc).__name__})",
                    parent=self,
                )
                return
        self.photo_service.discard_staged(self.photo_path.get())
        self._closing = True
        if self._ui_poll_id:
            try:
                self.after_cancel(self._ui_poll_id)
            except tk.TclError:
                pass
            self._ui_poll_id = None
        self.destroy()

    def _lookup_metadata(self):
        if self._active_operation is not None:
            return
        self._sync_provider_statuses()
        isbn = normalize_isbn(self._get("isbn"))
        if not isbn:
            self.metadata_status.set("Manual entry")
            self._reset_provider_statuses()
            self._update_control_states()
            return
        self._operation_serial += 1
        operation_id = self._operation_serial
        self._active_operation = ("lookup", operation_id, isbn)
        self.metadata_status.set("Looking up ISBN…")
        # Provider progress comes from the configured lookup chain. Keep every
        # provider at Not attempted until the service reports it as active.
        self._reset_provider_statuses()
        self._update_control_states()

        def report_provider(provider_name, status):
            self._schedule_ui(lambda: self._set_lookup_provider_status(operation_id, isbn, provider_name, status))

        def work():
            try:
                result = self.metadata_lookup.lookup(isbn, on_provider_status=report_provider)
            except Exception as exc:
                provider_statuses = {name: "Not attempted" for name in self._provider_names}
                if self._provider_names:
                    provider_statuses[self._provider_names[0]] = "Unexpected response error"
                result = MetadataResult(
                    "Lookup failed", {}, "Metadata providers", str(exc), "unexpected",
                    provider_statuses=provider_statuses,
                )
            self._schedule_ui(lambda: self._finish_lookup(operation_id, isbn, result))

        threading.Thread(target=work, name="BookLedgerMetadataLookup", daemon=True).start()

    def _isbn_changed(self):
        active = self._active_operation
        if not active or active[0] != "lookup" or normalize_isbn(self._get("isbn")) == active[2]:
            return
        # A different ISBN starts a different form request. Detach the old
        # operation immediately so its queued progress and result are ignored.
        self._active_operation = None
        self._reset_provider_statuses()
        self.metadata_status.set("Manual entry")
        self._update_control_states()

    def _set_lookup_provider_status(self, operation_id, requested_isbn, provider_name, status):
        if not self._active_operation or self._active_operation[1] != operation_id:
            return
        if normalize_isbn(self._get("isbn")) != requested_isbn:
            return
        self._set_provider_status(provider_name, status)

    def _reset_provider_statuses(self):
        for name in self._provider_names:
            self._set_provider_status(name, "Not attempted")

    def _finish_lookup(self, operation_id, requested_isbn, result):
        if not self._active_operation or self._active_operation[1] != operation_id:
            return
        current_isbn = normalize_isbn(self._get("isbn"))
        if current_isbn != requested_isbn:
            self._active_operation = None
            self._reset_provider_statuses()
            self.metadata_status.set("Manual entry")
            self._update_control_states()
            return

        self._reset_provider_statuses()
        for provider_name, status in result.provider_statuses.items():
            self._set_provider_status(provider_name, status)

        if result.values:
            self._apply_metadata(result)
        if result.status == "Retrieved" and result.values:
            summary = "Partially retrieved" if result.partial or result.failure_kind else "Metadata retrieved"
            detail = ""
            if result.values.get("book_details") in (None, "") and not self._get("book_details"):
                detail = " · Book Details unavailable"
            self.metadata_status.set(f"{summary} · {result.source or 'Metadata Providers'}{detail}")
        elif result.status == "No data":
            if result.failure_kind == "unverified":
                self.metadata_status.set(f"Results returned, but ISBN could not be confirmed · {result.source or 'Metadata Provider'}")
            elif result.record_found:
                self.metadata_status.set("Record found, but no usable supported metadata")
            else:
                self.metadata_status.set(f"No matching ISBN record · {result.source or 'Metadata Providers'}")
            self.metadata_source = result.source
        else:
            self.metadata_status.set(f"Metadata unavailable · {result.source or 'Metadata Providers'}")
            self.metadata_source = result.source
        if self.on_activity and (result.failure_kind or result.status in {"Lookup failed", "No data"}):
            self.on_activity("provider_lookup_failed", None)
        self._active_operation = None
        self._update_control_states()

    def _apply_metadata(self, result: MetadataResult):
        self.metadata_source = result.source
        optional = ("publisher", "publication_year", "edition", "page_count", "book_details", "srp")
        missing = [key.replace("_", " ").title() for key in optional if result.values.get(key) in (None, "") and not self._get(key)]
        self.metadata_status.set(f"Retrieved · {result.source or 'Metadata Provider'}" + (f" · No Data: {', '.join(missing)}" if missing else ""))
        for key in ("title", "author", "genre", "book_details", "publisher", "publication_year", "edition", "page_count", "format", "srp"):
            value = result.values.get(key)
            # Fill empty controls only, preserving manual or newer user input.
            if value not in (None, "") and key in self._widgets and not self._get(key):
                self._set(key, value)

    def _refresh(self):
        if self._active_operation is None and self.metadata_status.get().startswith("Metadata unavailable"):
            self._lookup_metadata()

    def _update_control_states(self):
        busy = self._active_operation is not None
        self.refresh_button.configure(state="disabled" if busy or not self._refreshable() else "normal")
        self.lookup_button.configure(state="disabled" if busy else "normal")

    def _refreshable(self):
        return self.metadata_status.get().startswith("Metadata unavailable")

    def _populate_validation(self, errors):
        for key, label in self._errors.items():
            label.configure(text=errors.get(key, ""))
            field_label = self._field_labels.get(key)
            if field_label is not None:
                field_label.configure(foreground="#b42318" if key in errors else "")
            widget = self._widgets.get(key)
            if widget is not None:
                try:
                    style = "Invalid.TCombobox" if isinstance(widget, ttk.Combobox) else "Invalid.TEntry"
                    widget.configure(style=style if key in errors else "TCombobox" if isinstance(widget, ttk.Combobox) else "TEntry")
                except tk.TclError:
                    pass
        self.error_summary.configure(text="Please correct the fields highlighted in red." if errors else "")

    def _clear_valid_error(self, key):
        if key not in self._errors or not self._errors[key].cget("text"):
            return
        current = {field: label.cget("text") for field, label in self._errors.items() if label.cget("text")}
        validation = self.service.validate(self._payload(), isbn_override=self.isbn_override.get())
        if key not in validation:
            current.pop(key, None)
            self._populate_validation(current)

    def _choose_no_isbn_match(self, matches):
        dialog = tk.Toplevel(self)
        dialog.title("Possible Duplicate Books")
        dialog.transient(self)
        dialog.grab_set()
        dialog.geometry("560x330")
        ttk.Label(dialog, text="Several records match this title and author.", font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=14, pady=(14, 4))
        ttk.Label(dialog, text="Choose an existing record to add another copy, or catalog this as a separate book.", wraplength=520).pack(anchor="w", padx=14, pady=(0, 10))
        listing = tk.Listbox(dialog, height=8, exportselection=False)
        listing.pack(fill="both", expand=True, padx=14, pady=(0, 10))
        for row in matches:
            listing.insert("end", f"Record #{row['id']} — {row['title']} / {row['author']} (No ISBN)")
        result = {"value": None}
        buttons = ttk.Frame(dialog, padding=(14, 0, 14, 14))
        buttons.pack(fill="x")

        def use_selected():
            selection = listing.curselection()
            if selection:
                result["value"] = matches[selection[0]]["id"]
                dialog.destroy()

        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side="right")
        ttk.Button(buttons, text="Create Separate Record", command=lambda: (result.update(value="separate"), dialog.destroy())).pack(side="right", padx=8)
        ttk.Button(buttons, text="Use Selected Record", command=use_selected).pack(side="right", padx=8)
        listing.selection_set(0)
        dialog.wait_window()
        return result["value"]

    def _payload(self):
        payload = {key: self._get(key) for key in self._widgets}
        payload["photo_path"] = self.photo_path.get().strip()
        payload["isbn"] = normalize_isbn(payload.get("isbn"))
        payload["location"] = payload.get("location") or DEFAULT_LOCATION
        payload["metadata_source"] = self.metadata_source
        payload["metadata_status"] = self.metadata_status.get().split(" · ")[0]
        return payload

    def _save_copy(self, payload, existing_book_id=None):
        try:
            self.service.create_copy(
                payload,
                isbn_override=self.isbn_override.get(),
                existing_book_id=existing_book_id,
                copy_uuid=self.incoming_copy_uuid,
            )
            if existing_book_id is None:
                self._new_book_record_created = True
            return True
        except ValidationError as exc:
            self._populate_validation(exc.errors)
            if self.on_activity:
                self.on_activity("book_save_failed", None)
            return False

    def _save(self):
        try:
            return self._save_book()
        except Exception:
            if self.on_activity:
                self.on_activity("book_save_failed", None)
            raise

    def _save_book(self):
        self._new_book_record_created = False
        payload = self._payload()
        errors = self.service.validate(payload, isbn_override=self.isbn_override.get())
        if errors:
            self._populate_validation(errors)
            if self.on_activity:
                self.on_activity("book_save_failed", None)
            return
        if self.existing:
            try:
                self.service.update_copy(self.existing["copy_id"], payload, isbn_override=self.isbn_override.get())
            except ValidationError as exc:
                self._populate_validation(exc.errors)
                if self.on_activity:
                    self.on_activity("book_save_failed", None)
                return
        else:
            isbn = payload.get("isbn")
            existing_book = self.service.duplicate_by_isbn(isbn) if isbn else None
            if existing_book:
                if not messagebox.askyesno("Existing ISBN", "This ISBN already exists. Add another physical copy using the existing bibliographic record?", parent=self):
                    self._populate_validation({"isbn": "Review the existing record or use a different ISBN."})
                    return
                if not self._save_copy(payload, existing_book_id=existing_book["id"]):
                    return
            elif not isbn:
                matches = self.service.no_isbn_title_author_matches(payload["title"], payload["author"])
                if matches:
                    if len(matches) == 1:
                        chosen = matches[0]
                        if messagebox.askyesno("Possible Duplicate", "A book with this title and author already exists without an ISBN. Add this as another physical copy of that record?", parent=self):
                            if not self._save_copy(payload, existing_book_id=chosen["id"]):
                                return
                        elif not self._save_copy(payload):
                            return
                    else:
                        choice = self._choose_no_isbn_match(matches)
                        if choice == "separate":
                            if not self._save_copy(payload):
                                return
                        elif choice is not None:
                            if not self._save_copy(payload, existing_book_id=choice):
                                return
                        else:
                            return
                elif not self._save_copy(payload):
                    return
            elif not self._save_copy(payload):
                return
        if self.on_activity:
            if self.existing:
                self.on_activity("physical_copy_edited", int(self.existing["copy_id"]))
            else:
                self.on_activity("physical_copy_added", None)
                if self._new_book_record_created:
                    self.on_activity("book_added", None)
        self._incoming_sequence_finished = True
        self.on_saved()
        self.photo_service.discard_staged(self.photo_path.get())
        self._close()

    def _has_input(self):
        defaults = {"location": DEFAULT_LOCATION}
        return any(self._get(key) != defaults.get(key, "") for key in self._widgets) or bool(self.photo_path.get())

    def _clear(self):
        if self.incoming_capture_id:
            self._discard_incoming()
            return
        if self._has_input() and not messagebox.askyesno(
            "Clear Book Form?", "Discard the current unsaved entries and reset the form?", parent=self
        ):
            return
        if self._active_operation is not None:
            # Detach the lookup so queued progress and results are ignored.
            self._active_operation = None
        for key in self._widgets:
            self._set(key, "")
        self.photo_service.discard_staged(self.photo_path.get())
        self.photo_path.set("")
        self.photo_path_label.configure(text="No Photo Selected")
        self._photo_image = None
        self.photo_preview.configure(image="", text="No Photo Selected")
        self.isbn_override.set(False)
        self.metadata_source = None
        self.metadata_status.set("Manual entry")
        self._reset_provider_statuses()
        self._set("location", DEFAULT_LOCATION)
        self._populate_validation({})
        self._update_control_states()
