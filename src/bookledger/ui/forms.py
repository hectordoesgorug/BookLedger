from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from queue import Empty, SimpleQueue
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from bookledger.config import APPROVED_GENRES, DEFAULT_LOCATION
from bookledger.services.catalog import CatalogService, ValidationError
from bookledger.services.isbn import isbn_check, normalize_isbn
from bookledger.services.metadata import MetadataLookupService, MetadataResult

NO_DATA = "No Data"
OPTIONAL_METADATA_FIELDS = frozenset({"publisher", "publication_year", "edition", "page_count", "srp", "book_details"})


class BookForm(tk.Toplevel):
    """Add/edit form with a testable BookLedger Mobile intake simulation."""

    def __init__(
        self,
        parent,
        *,
        service: CatalogService,
        photo_service,
        on_saved,
        existing=None,
        existing_book_id=None,
        metadata_lookup: MetadataLookupService | None = None,
    ):
        super().__init__(parent)
        self.parent = parent
        self.service = service
        self.photo_service = photo_service
        self.on_saved = on_saved
        self.existing = existing
        self.existing_book_id = existing_book_id
        self.metadata_lookup = metadata_lookup or MetadataLookupService()
        self.photo_path = tk.StringVar(value="")
        self.isbn_override = tk.BooleanVar(value=False)
        self.metadata_status = tk.StringVar(value="Manual entry")
        self.open_library_status = tk.StringVar(value="Not attempted")
        self.google_books_status = tk.StringVar(value="Not attempted")
        self.mobile_status = tk.StringVar(value="Idle — Ready")
        self.connection_outcome = tk.StringVar(value="Connected — Ready")
        self.mock_scan_isbn = tk.StringVar()
        self.metadata_source = (existing or {}).get("metadata_source")
        self._widgets = {}
        self._errors = {}
        self._field_labels = {}
        self._active_operation = None
        self._operation_serial = 0
        self._invalidated_operations = set()  # Used by simulated connection/scan callbacks.
        self._photo_image = None
        self._scan_timeout_id = None
        self._connection_ready = False
        self._ui_queue = SimpleQueue()
        self._ui_poll_id = None
        self._closing = False

        self.title("Edit Book" if existing else "Add Book")
        self.geometry("1120x850")
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
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(self._form_canvas_window, width=event.width))
        self.body = body
        body.columnconfigure(1, weight=1)

        row = 0
        ttk.Label(body, text="Bibliographic Details", font=("Segoe UI", 12, "bold")).grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 8))
        row += 1
        row = self._field(body, "Title", "title", row, required=True)
        row = self._field(body, "Author", "author", row, required=True)
        row = self._field(body, "ISBN (Optional)", "isbn", row)
        self.isbn_controls = ttk.Frame(body)
        self.isbn_controls.grid(row=row, column=1, sticky="w", pady=(0, 6))
        row += 1
        self.lookup_button = ttk.Button(self.isbn_controls, text="Look Up ISBN", command=self._lookup_metadata)
        self.lookup_button.pack(side="left")
        ttk.Checkbutton(
            self.isbn_controls,
            text="Override ISBN Validation",
            variable=self.isbn_override,
        ).pack(side="left", padx=(10, 0))
        row = self._field(body, "Genre", "genre", row, required=True, values=APPROVED_GENRES)
        row = self._field(body, "Publisher/Imprint", "publisher", row)
        row = self._field(body, "Publication Year", "publication_year", row)
        row = self._field(body, "Edition", "edition", row)
        row = self._field(body, "Page Count", "page_count", row)
        row = self._field(body, "SRP (PHP, Reference Only)", "srp", row, read_only=True)
        row = self._multiline_field(body, "Book Details/Synopsis", "book_details", row)

        ttk.Label(body, text="Physical Copy", font=("Segoe UI", 12, "bold")).grid(row=row, column=0, columnspan=2, sticky="w", pady=(18, 8))
        row += 1
        row = self._field(body, "Format", "format", row, required=True, values=("Paperback", "Hardcover", "Mass Market Paperback", "Board Book", "Other"))
        row = self._field(body, "Condition", "condition", row, required=True, values=("Like New", "Very Good", "Good", "Acceptable", "Poor"))
        row = self._field(body, "Location", "location", row, values=self.service.list_locations())
        row = self._field(body, "Price (PHP)", "price", row, required=True)
        row = self._photo_row(body, row)

        self.metadata_status_panel = ttk.Frame(body)
        self.metadata_status_panel.grid(row=row, column=0, columnspan=2, sticky="w", pady=(12, 2))
        self.metadata_label = ttk.Label(self.metadata_status_panel, textvariable=self.metadata_status, foreground="#334155")
        self.metadata_label.grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(self.metadata_status_panel, text="Open Library:", foreground="#596579").grid(row=1, column=0, sticky="w", padx=(0, 4))
        self.open_library_label = ttk.Label(self.metadata_status_panel, textvariable=self.open_library_status, foreground="#596579")
        self.open_library_label.grid(row=1, column=1, sticky="w")
        ttk.Label(self.metadata_status_panel, text="Google Books:", foreground="#596579").grid(row=2, column=0, sticky="w", padx=(0, 4))
        self.google_books_label = ttk.Label(self.metadata_status_panel, textvariable=self.google_books_status, foreground="#596579")
        self.google_books_label.grid(row=2, column=1, sticky="w")
        row += 1
        ttk.Label(body, text="Fields marked * are required. Metadata lookup is optional.", foreground="#596579").grid(
            row=row, column=0, columnspan=2, sticky="w"
        )
        row += 1
        self.error_summary = ttk.Label(body, text="", foreground="#b42318", wraplength=620)
        self.error_summary.grid(row=row, column=0, columnspan=2, sticky="w", pady=(6, 0))

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
        ttk.Label(
            self.photo_panel,
            text="Reserved for a future BookLedger Mobile photo.",
            wraplength=220,
            foreground="#596579",
        ).pack(anchor="w", pady=(10, 0))

        self._build_mobile_status(self.right_panel)
        self._build_actions(self.right_panel)
        self._update_control_states()

    def _field(self, parent, label, key, row, *, required=False, values=None, read_only=False):
        field_label = ttk.Label(parent, text=f"{label} *" if required else label)
        field_label.grid(row=row, column=0, sticky="w", padx=(0, 10), pady=4)
        self._field_labels[key] = field_label
        if values:
            widget = ttk.Combobox(parent, values=values, width=32)
            if key != "genre":
                widget.configure(state="readonly")
        else:
            widget = ttk.Entry(parent, width=34)
            if read_only:
                widget.configure(state="readonly")
        widget.grid(row=row, column=1, sticky="ew", pady=4)
        parent.grid_columnconfigure(1, weight=1)
        self._widgets[key] = widget
        error = ttk.Label(parent, text="", foreground="#b42318", wraplength=560)
        error.grid(row=row + 1, column=1, sticky="w", pady=(0, 3))
        self._errors[key] = error
        widget.bind("<KeyRelease>", lambda _event, field=key: self._clear_valid_error(field), add="+")
        if key == "isbn":
            widget.bind("<KeyRelease>", lambda _event: self._isbn_changed(), add="+")
        if key in OPTIONAL_METADATA_FIELDS and key != "srp":
            widget.bind("<FocusIn>", lambda _event, field=key: self._clear_placeholder(field), add="+")
            widget.bind("<FocusOut>", lambda _event, field=key: self._restore_placeholder(field), add="+")
        if isinstance(widget, ttk.Combobox):
            widget.bind("<<ComboboxSelected>>", lambda _event, field=key: self._clear_valid_error(field), add="+")
        return row + 2

    def _multiline_field(self, parent, label, key, row):
        field_label = ttk.Label(parent, text=label)
        field_label.grid(row=row, column=0, sticky="nw", padx=(0, 10), pady=4)
        widget = tk.Text(parent, height=3, width=34, wrap="word", relief="solid", borderwidth=1)
        widget.grid(row=row, column=1, sticky="ew", pady=4)
        parent.grid_columnconfigure(1, weight=1)
        self._widgets[key] = widget
        error = ttk.Label(parent, text="", foreground="#b42318", wraplength=560)
        error.grid(row=row + 1, column=1, sticky="w", pady=(0, 3))
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
        controls.grid(row=row, column=1, sticky="ew", pady=4)
        self.photo_path_label = ttk.Label(controls, text="No Photo Selected", width=25)
        self.photo_path_label.pack(side="left", fill="x", expand=True)
        ttk.Button(controls, text="Choose Photo", command=self._choose_photo).pack(side="left", padx=(8, 0))
        self._errors["photo_path"] = ttk.Label(parent, text="", foreground="#b42318", wraplength=560)
        self._errors["photo_path"].grid(row=row + 1, column=1, sticky="w", pady=(0, 3))
        return row + 2

    def _build_mobile_status(self, parent):
        panel = ttk.LabelFrame(parent, text="BookLedger Mobile (Simulation)", padding=(10, 8))
        self.mobile_panel = panel
        panel.grid(row=1, column=0, sticky="ew", pady=(10, 8))
        panel.columnconfigure(1, weight=1)
        ttk.Label(panel, text="Status:").grid(row=0, column=0, sticky="w", padx=(0, 6))
        ttk.Label(panel, textvariable=self.mobile_status, foreground="#334155").grid(row=0, column=1, sticky="w")

        ttk.Label(panel, text="Connection Outcome").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.connection_outcome_box = ttk.Combobox(
            panel,
            textvariable=self.connection_outcome,
            values=("Connected — Ready", "Connection Failed"),
            state="readonly",
            width=18,
        )
        self.connection_outcome_box.grid(row=1, column=1, sticky="ew", pady=(8, 0))
        self.connect_button = ttk.Button(panel, text="Simulate Connection", command=self._simulate_connection)
        self.connect_button.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(5, 0))

        ttk.Label(panel, text="Mock Scan ISBN").grid(row=3, column=0, sticky="w", pady=(8, 0))
        self.mock_scan_entry = ttk.Entry(panel, textvariable=self.mock_scan_isbn, width=18)
        self.mock_scan_entry.grid(row=3, column=1, sticky="ew", pady=(8, 0))
        self.scan_button = ttk.Button(panel, text="Simulate Scan", command=self._simulate_scan)
        self.scan_button.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(5, 0))

    def _build_actions(self, parent):
        actions = ttk.Frame(parent)
        self.actions_panel = actions
        actions.grid(row=2, column=0, sticky="ew")
        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(1, weight=1)
        self.save_button = ttk.Button(actions, text="Save Book", command=self._save)
        self.refresh_button = ttk.Button(actions, text="Refresh", command=self._refresh)
        self.clear_button = ttk.Button(actions, text="Clear", command=self._clear)
        self.cancel_button = ttk.Button(actions, text="Cancel", command=self._close)
        self.save_button.grid(row=0, column=0, sticky="ew", padx=(0, 5), pady=(0, 5))
        self.refresh_button.grid(row=0, column=1, sticky="ew", padx=(5, 0), pady=(0, 5))
        self.clear_button.grid(row=1, column=0, sticky="ew", padx=(0, 5))
        self.cancel_button.grid(row=1, column=1, sticky="ew", padx=(5, 0))

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
        """Set an already stored photo; this is the handoff point for future mobile capture."""
        self.photo_path.set(str(value))
        self.photo_path_label.configure(text=Path(value).name or str(value))
        try:
            with Image.open(self._resolve_photo(value)) as source:
                image = source.convert("RGB")
                image.thumbnail((240, 320), Image.Resampling.LANCZOS)
                self._photo_image = ImageTk.PhotoImage(image)
            self.photo_preview.configure(image=self._photo_image, text="")
        except (OSError, tk.TclError):
            self._photo_image = None
            self.photo_preview.configure(image="", text="Photo Preview Unavailable")
        self._clear_valid_error("photo_path")

    def receive_photo(self, value: str | Path):
        """Accept a photo path from a future companion event without networking here."""
        try:
            staged = self.photo_service.import_and_compress(value)
            self._replace_staged_photo(staged)
            self.set_photo(staged)
            self.mobile_status.set("Photo Received")
            self._update_control_states()
        except ValueError as exc:
            self._populate_validation({"photo_path": str(exc)})

    def _replace_staged_photo(self, new_path):
        previous = self.photo_path.get()
        if previous and Path(previous) != Path(new_path):
            self.photo_service.discard_staged(previous)

    def phone_photo_capture_started(self):
        """Status hook for a future mobile capture event; no phone capture is performed here."""
        self.mobile_status.set("Taking Photo…")
        self._update_control_states()

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

    def _close(self):
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
        isbn = normalize_isbn(self._get("isbn"))
        if not isbn:
            self.metadata_status.set("Manual entry")
            self._reset_provider_statuses()
            self.mobile_status.set("Idle — Ready")
            self._update_control_states()
            return
        self._operation_serial += 1
        operation_id = self._operation_serial
        self._active_operation = ("lookup", operation_id, isbn)
        self.metadata_status.set("Looking up ISBN…")
        self.open_library_status.set("Retrieving from Open Library…")
        self.google_books_status.set("Waiting for Open Library…")
        self._update_control_states()

        def report_provider(provider_name, status):
            self._schedule_ui(lambda: self._set_lookup_provider_status(operation_id, isbn, provider_name, status))

        def work():
            try:
                result = self.metadata_lookup.lookup(isbn, on_provider_status=report_provider)
            except Exception as exc:
                result = MetadataResult(
                    "Lookup failed", {}, "Metadata providers", str(exc), "unexpected",
                    provider_statuses={"Open Library": "Unexpected response error", "Google Books": "Not attempted"},
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
        self.mobile_status.set("Connected — Ready" if self._connection_ready else "Idle — Ready")
        self._update_control_states()

    def _set_lookup_provider_status(self, operation_id, requested_isbn, provider_name, status):
        if not self._active_operation or self._active_operation[1] != operation_id:
            return
        if normalize_isbn(self._get("isbn")) != requested_isbn:
            return
        target = {
            "Open Library": self.open_library_status,
            "Google Books": self.google_books_status,
        }.get(provider_name)
        if target is not None:
            target.set(status)

    def _reset_provider_statuses(self):
        self.open_library_status.set("Not attempted")
        self.google_books_status.set("Not attempted")

    def _finish_lookup(self, operation_id, requested_isbn, result):
        if not self._active_operation or self._active_operation[1] != operation_id:
            return
        current_isbn = normalize_isbn(self._get("isbn"))
        if current_isbn != requested_isbn:
            self._active_operation = None
            self._reset_provider_statuses()
            self.metadata_status.set("Manual entry")
            self._update_control_states()
            self.mobile_status.set("Connected — Ready" if self._connection_ready else "Idle — Ready")
            return

        self._reset_provider_statuses()
        for provider_name, status in result.provider_statuses.items():
            target = {
                "Open Library": self.open_library_status,
                "Google Books": self.google_books_status,
            }.get(provider_name)
            if target is not None:
                target.set(status)

        if result.values:
            self._apply_metadata(result)
        if result.status == "Retrieved" and result.values:
            summary = "Partially retrieved" if result.partial or result.failure_kind else "Metadata retrieved"
            self.metadata_status.set(f"{summary} · {result.source or 'Metadata Providers'}")
        elif result.status == "No data":
            if result.record_found:
                self.metadata_status.set("Record found, but no usable supported metadata")
            else:
                self.metadata_status.set(f"No matching ISBN record · {result.source or 'Metadata Providers'}")
            self.metadata_source = result.source
        else:
            self.metadata_status.set(f"Metadata unavailable · {result.source or 'Metadata Providers'}")
            self.metadata_source = result.source
        self.mobile_status.set("Connected — Ready" if self._connection_ready else "Idle — Ready")
        self._active_operation = None
        self._update_control_states()

    def _apply_metadata(self, result: MetadataResult):
        self.metadata_source = result.source
        optional = ("publisher", "publication_year", "edition", "page_count", "book_details", "srp")
        missing = [key.replace("_", " ").title() for key in optional if result.values.get(key) in (None, "") and not self._get(key)]
        self.metadata_status.set(f"Retrieved · {result.source or 'Metadata Provider'}" + (f" · No Data: {', '.join(missing)}" if missing else ""))
        for key in ("title", "author", "genre", "book_details", "publisher", "publication_year", "edition", "page_count", "srp"):
            value = result.values.get(key)
            # Fill empty controls only, preserving manual or newer user input.
            if value not in (None, "") and key in self._widgets and not self._get(key):
                self._set(key, value)

    def _simulate_connection(self):
        if self._active_operation is not None:
            return
        self._operation_serial += 1
        operation_id = self._operation_serial
        self._active_operation = ("connection", operation_id, None)
        self.mobile_status.set("Connecting to App…")
        self._update_control_states()
        self.after(200, lambda: self._finish_connection(operation_id))

    def _finish_connection(self, operation_id):
        if not self._active_operation or self._active_operation[1] != operation_id:
            return
        self._active_operation = None
        if operation_id in self._invalidated_operations:
            self._invalidated_operations.discard(operation_id)
            self._update_control_states()
            return
        self._connection_ready = self.connection_outcome.get() == "Connected — Ready"
        self.mobile_status.set("Connected — Ready" if self._connection_ready else "Connection Failed")
        self._update_control_states()

    def _simulate_scan(self):
        if self._active_operation is not None or not self._connection_ready:
            return
        self._operation_serial += 1
        operation_id = self._operation_serial
        self._active_operation = ("scan", operation_id, None)
        self.mobile_status.set("Scanning ISBN…")
        self._update_control_states()
        self._scan_timeout_id = self.after(10_000, lambda: self._finish_scan(operation_id, None))
        mock_isbn = self.mock_scan_isbn.get().strip()
        if mock_isbn:
            self.after(200, lambda: self._finish_scan(operation_id, mock_isbn))

    def _finish_scan(self, operation_id, value):
        if not self._active_operation or self._active_operation[1] != operation_id:
            return
        if self._scan_timeout_id:
            try:
                self.after_cancel(self._scan_timeout_id)
            except tk.TclError:
                pass
            self._scan_timeout_id = None
        self._active_operation = None
        if operation_id in self._invalidated_operations:
            self._invalidated_operations.discard(operation_id)
            self._update_control_states()
            return
        if value:
            valid, _message = isbn_check(value)
            if valid and normalize_isbn(value):
                self._set("isbn", normalize_isbn(value))
                self.mobile_status.set("Connected — Ready")
            else:
                self.mobile_status.set("Scan Failed")
        else:
            self.mobile_status.set("Scan Failed")
        self._update_control_states()

    def _refresh(self):
        if self._active_operation is not None:
            return
        status = self.mobile_status.get()
        if status == "Connection Failed":
            self._simulate_connection()
        elif status == "Scan Failed":
            self._simulate_scan()
        elif self.metadata_status.get().startswith("Metadata unavailable"):
            self._lookup_metadata()

    def _update_control_states(self):
        busy = self._active_operation is not None
        self.refresh_button.configure(state="disabled" if busy or not self._refreshable() else "normal")
        self.lookup_button.configure(state="disabled" if busy else "normal")
        self.connect_button.configure(state="disabled" if busy else "normal")
        self.scan_button.configure(state="normal" if self._connection_ready and not busy else "disabled")

    def _refreshable(self):
        status = self.mobile_status.get()
        return status in {"Connection Failed", "Scan Failed"} or self.metadata_status.get().startswith("Metadata unavailable")

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
            )
            return True
        except ValidationError as exc:
            self._populate_validation(exc.errors)
            return False

    def _save(self):
        payload = self._payload()
        errors = self.service.validate(payload, isbn_override=self.isbn_override.get())
        if errors:
            self._populate_validation(errors)
            return
        if self.existing:
            try:
                self.service.update_copy(self.existing["copy_id"], payload, isbn_override=self.isbn_override.get())
            except ValidationError as exc:
                self._populate_validation(exc.errors)
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
        self.on_saved()
        self.photo_service.discard_staged(self.photo_path.get())
        self._close()

    def _has_input(self):
        defaults = {"location": DEFAULT_LOCATION}
        return any(self._get(key) != defaults.get(key, "") for key in self._widgets) or bool(self.photo_path.get())

    def _clear(self):
        if self._has_input() and not messagebox.askyesno(
            "Clear Book Form?", "Discard the current unsaved entries and reset the form?", parent=self
        ):
            return
        if self._active_operation is not None:
            kind, operation_id, _requested_isbn = self._active_operation
            if kind == "lookup":
                # Detach now so Clear can start a fresh lookup immediately.
                # Any queued callbacks from this operation will fail the ID check.
                self._active_operation = None
            else:
                if self._scan_timeout_id:
                    try:
                        self.after_cancel(self._scan_timeout_id)
                    except tk.TclError:
                        pass
                    self._scan_timeout_id = None
                self._active_operation = None
        for key in self._widgets:
            self._set(key, "")
        self.photo_service.discard_staged(self.photo_path.get())
        self.photo_path.set("")
        self.photo_path_label.configure(text="No Photo Selected")
        self._photo_image = None
        self.photo_preview.configure(image="", text="No Photo Selected")
        self.isbn_override.set(False)
        self.mock_scan_isbn.set("")
        self.metadata_source = None
        self.metadata_status.set("Manual entry")
        self._reset_provider_statuses()
        self._connection_ready = False
        self.mobile_status.set("Idle — Ready")
        self._set("location", DEFAULT_LOCATION)
        self._populate_validation({})
        self._update_control_states()
