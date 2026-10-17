from __future__ import annotations
import threading
import tkinter as tk
from tkinter import ttk, filedialog
from datetime import date
from pathlib import Path

from bookledger.config import APPROVED_GENRES, COPY_STATUSES, DEFAULT_LOCATION
from bookledger.services.catalog import CatalogService, ValidationError
from bookledger.services.isbn import isbn_check, normalize_isbn
from bookledger.services.metadata import GoogleBooksProvider


class BookForm(tk.Toplevel):
    """Intake/Edit form. Validation errors stay inline; no validation modal dialogs."""
    def __init__(self, parent, *, service: CatalogService, photo_service, on_saved, existing=None, existing_book_id=None):
        super().__init__(parent)
        self.parent = parent
        self.service = service
        self.photo_service = photo_service
        self.on_saved = on_saved
        self.existing = existing
        self.existing_book_id = existing_book_id
        self.photo_path = tk.StringVar(value=(existing or {}).get("photo_path", ""))
        self.isbn_override = tk.BooleanVar(value=False)
        self.metadata_status = tk.StringVar(value=(existing or {}).get("metadata_status", "Manual entry"))
        self.metadata_source = (existing or {}).get("metadata_source")
        self._widgets = {}
        self._errors = {}
        self._field_labels = {}
        self.title("Edit Book" if existing else "Add Book")
        self.geometry("880x780")
        self.minsize(760, 650)
        self.transient(parent)
        self.grab_set()
        self._build()
        if existing:
            self._populate(existing)
        else:
            self._set("location", DEFAULT_LOCATION)
            self._set("status", "Available")
            self._widgets["status"].configure(state="disabled")
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _build(self):
        outer = ttk.Frame(self, padding=16)
        outer.pack(fill="both", expand=True)
        canvas = tk.Canvas(outer, highlightthickness=0)
        scrollbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        body = ttk.Frame(canvas)
        body.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=body, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.body = body

        ttk.Label(body, text="Bibliographic details", font=("Segoe UI", 12, "bold")).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 8))
        self._field(body, "Title", "title", 1, required=True)
        self._field(body, "Author", "author", 2, required=True)
        self._field(body, "ISBN (optional)", "isbn", 3)
        ttk.Button(body, text="Look up ISBN", command=self._lookup_metadata).grid(row=3, column=2, sticky="w", padx=6)
        ttk.Checkbutton(body, text="Override ISBN validation", variable=self.isbn_override).grid(row=3, column=3, sticky="w")
        self._field(body, "Genre", "genre", 4, required=True, values=APPROVED_GENRES)
        self._field(body, "Publisher / imprint", "publisher", 5)
        self._field(body, "Publication year", "publication_year", 6)
        self._field(body, "Edition", "edition", 7)
        self._field(body, "Page count", "page_count", 8)
        self._field(body, "SRP (PHP, reference only)", "srp", 9)
        self._field(body, "Book Details / synopsis", "book_details", 10, multiline=True)

        ttk.Label(body, text="Physical copy", font=("Segoe UI", 12, "bold")).grid(row=11, column=0, columnspan=4, sticky="w", pady=(18, 8))
        self._field(body, "Format", "format", 12, required=True, values=("Paperback", "Hardcover", "Mass market paperback", "Board book", "Other"))
        self._field(body, "Condition", "condition", 13, required=True, values=("Like New", "Very Good", "Good", "Acceptable", "Poor"))
        self._field(body, "Location", "location", 14)
        self._field(body, "Price (PHP)", "price", 15, required=True)
        self._field(body, "Status", "status", 16, values=COPY_STATUSES)
        self._photo_row(body, 17)
        self._field(body, "Actual sale price (PHP)", "actual_sale_price", 19)
        self._field(body, "Sale date (YYYY-MM-DD)", "sale_date", 20)
        ttk.Label(body, textvariable=self.metadata_status, foreground="#596579").grid(row=21, column=0, columnspan=4, sticky="w", pady=(12, 2))
        ttk.Label(body, text="Fields marked * are required. Metadata lookup is optional.", foreground="#596579").grid(row=22, column=0, columnspan=4, sticky="w")
        self.error_summary = ttk.Label(body, text="", foreground="#b42318", wraplength=780)
        self.error_summary.grid(row=23, column=0, columnspan=4, sticky="w", pady=(6, 0))
        buttons = ttk.Frame(outer)
        buttons.pack(fill="x", pady=(12, 0))
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(buttons, text="Save Book", command=self._save).pack(side="right", padx=(0, 8))

    def _field(self, parent, label, key, row, *, required=False, values=None, multiline=False):
        label_text = f"{label} *" if required else label
        field_label = ttk.Label(parent, text=label_text)
        field_label.grid(row=row, column=0, sticky="w", padx=(0, 12), pady=4)
        self._field_labels[key] = field_label
        if multiline:
            widget = tk.Text(parent, height=3, width=50, wrap="word", relief="solid", borderwidth=1)
            widget.grid(row=row, column=1, columnspan=3, sticky="ew", pady=4)
        elif values:
            widget = ttk.Combobox(parent, values=values, width=34)
            # Genre stays editable so a provider's unknown value can be shown and then rejected inline.
            if key != "genre":
                widget.configure(state="readonly")
            widget.grid(row=row, column=1, sticky="ew", pady=4)
        else:
            widget = ttk.Entry(parent, width=38)
            widget.grid(row=row, column=1, sticky="ew", pady=4)
        self._widgets[key] = widget
        error = ttk.Label(parent, text="", foreground="#b42318", wraplength=290)
        error.grid(row=row, column=2, columnspan=2, sticky="w", padx=6)
        self._errors[key] = error
        parent.grid_columnconfigure(1, weight=1)

    def _photo_row(self, parent, row):
        photo_label = ttk.Label(parent, text="Copy photo *")
        photo_label.grid(row=row, column=0, sticky="w", padx=(0, 12), pady=4)
        self._field_labels["photo_path"] = photo_label
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=1, columnspan=3, sticky="ew", pady=4)
        ttk.Label(frame, textvariable=self.photo_path, width=48).pack(side="left", fill="x", expand=True)
        ttk.Button(frame, text="Choose Photo…", command=self._choose_photo).pack(side="left", padx=4)
        self._errors["photo_path"] = ttk.Label(parent, text="", foreground="#b42318")
        self._errors["photo_path"].grid(row=row + 1, column=1, columnspan=3, sticky="w")

    def _set(self, key, value):
        widget = self._widgets.get(key)
        if widget is None:
            return
        if isinstance(widget, tk.Text):
            widget.delete("1.0", "end")
            widget.insert("1.0", value or "")
        else:
            widget.configure(state="normal")
            widget.delete(0, "end")
            widget.insert(0, "" if value is None else str(value))
            if isinstance(widget, ttk.Combobox) and key != "genre":
                widget.configure(state="readonly")

    def _get(self, key):
        widget = self._widgets[key]
        if isinstance(widget, tk.Text):
            return widget.get("1.0", "end-1c").strip()
        return widget.get().strip()

    def _populate(self, row):
        for key in ("title", "author", "isbn", "genre", "publisher", "publication_year", "edition", "page_count", "book_details", "format", "condition", "location", "status", "sale_date"):
            self._set(key, row.get(key))
        self._set("price", f"{row.get('price_minor', 0) / 100:.2f}")
        self._set("srp", f"{row['srp_minor'] / 100:.2f}" if row.get("srp_minor") is not None else "")
        self._set("actual_sale_price", f"{row['actual_sale_price_minor'] / 100:.2f}" if row.get("actual_sale_price_minor") is not None else "")

    def _choose_photo(self):
        path = filedialog.askopenfilename(parent=self, title="Choose a book photo", filetypes=[("Images", "*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff"), ("All files", "*.*")])
        if not path:
            return
        try:
            compressed = self.photo_service.import_and_compress(path)
            self.photo_path.set(str(compressed))
            self._errors["photo_path"].configure(text="")
        except ValueError as exc:
            self._errors["photo_path"].configure(text=str(exc))

    def _lookup_metadata(self):
        isbn = normalize_isbn(self._get("isbn"))
        if not isbn:
            self.metadata_status.set("Manual entry — enter an ISBN to look up metadata.")
            return
        self.metadata_status.set("Retrieving…")
        def work():
            result = GoogleBooksProvider().lookup(isbn)
            self.after(0, lambda: self._apply_metadata(result))
        threading.Thread(target=work, daemon=True).start()

    def _apply_metadata(self, result):
        self.metadata_status.set(result.status if not result.error else f"Lookup failed — {result.error}")
        self.metadata_source = result.source
        self.metadata_status.set(f"{result.status} · {result.source or 'No provider'}")
        for key in ("title", "author", "isbn", "genre", "book_details", "publisher", "publication_year", "page_count"):
            value = result.values.get(key)
            if value not in (None, ""):
                self._set(key, value)
        # A provider-returned unfamiliar genre remains visible and will fail validation until recategorized.

    def _payload(self):
        payload = {key: self._get(key) for key in self._widgets}
        payload["photo_path"] = self.photo_path.get().strip()
        payload["isbn"] = normalize_isbn(payload.get("isbn"))
        payload["location"] = payload.get("location") or DEFAULT_LOCATION
        payload["metadata_source"] = self.metadata_source
        payload["metadata_status"] = self.metadata_status.get().split(" · ")[0]
        return payload

    def _highlight(self, errors):
        for key, label in self._errors.items():
            label.configure(text=errors.get(key, ""))
            field_label = self._field_labels.get(key)
            if field_label is not None:
                field_label.configure(foreground="#b42318" if key in errors else "")
            widget = self._widgets.get(key)
            if widget is not None:
                try:
                    invalid_style = "Invalid.TCombobox" if isinstance(widget, ttk.Combobox) else "Invalid.TEntry"
                    normal_style = "TCombobox" if isinstance(widget, ttk.Combobox) else "TEntry"
                    widget.configure(style=invalid_style if key in errors else normal_style)
                except tk.TclError:
                    pass
        self.error_summary.configure(text="Please correct the fields highlighted in red." if errors else "")

    def _choose_no_isbn_match(self, matches):
        dialog = tk.Toplevel(self)
        dialog.title("Possible duplicate books")
        dialog.transient(self)
        dialog.grab_set()
        dialog.geometry("560x330")
        ttk.Label(dialog, text="Several records match this title and author.", font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=14, pady=(14, 4))
        ttk.Label(dialog, text="Choose an existing record to add another copy, or catalog this as a separate book.", wraplength=520).pack(anchor="w", padx=14, pady=(0, 10))
        listing = tk.Listbox(dialog, height=8, exportselection=False)
        listing.pack(fill="both", expand=True, padx=14, pady=(0, 10))
        for row in matches:
            listing.insert("end", f"Record #{row['id']}  —  {row['title']} / {row['author']}  (no ISBN)")
        result = {"value": None}
        buttons = ttk.Frame(dialog, padding=(14, 0, 14, 14))
        buttons.pack(fill="x")
        def use_selected():
            selection = listing.curselection()
            if selection:
                result["value"] = matches[selection[0]]["id"]
                dialog.destroy()
        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side="right")
        ttk.Button(buttons, text="Create separate record", command=lambda: (result.update(value="separate"), dialog.destroy())).pack(side="right", padx=8)
        ttk.Button(buttons, text="Use selected record", command=use_selected).pack(side="right", padx=8)
        listing.selection_set(0)
        dialog.wait_window()
        return result["value"]

    def _save(self):
        payload = self._payload()
        errors = self.service.validate(payload, isbn_override=self.isbn_override.get())
        if errors:
            self._highlight(errors)
            return
        if self.existing:
            try:
                self.service.update_copy(self.existing["copy_id"], payload, isbn_override=self.isbn_override.get())
            except ValidationError as exc:
                self._highlight(exc.errors)
                return
        else:
            isbn = payload.get("isbn")
            existing_book = self.service.duplicate_by_isbn(isbn) if isbn else None
            if existing_book:
                from tkinter import messagebox
                if not messagebox.askyesno("Existing ISBN", "This ISBN already exists. Add another physical copy using the existing bibliographic record?", parent=self):
                    self._highlight({"isbn": "Review the existing record or use a different ISBN."})
                    return
                try:
                    self.service.create_copy(payload, isbn_override=self.isbn_override.get(), existing_book_id=existing_book["id"])
                except ValidationError as exc:
                    self._highlight(exc.errors)
                    return
            else:
                # No-ISBN duplicate candidates require a deliberate user decision.
                if not isbn:
                    matches = self.service.no_isbn_title_author_matches(payload["title"], payload["author"])
                    if matches:
                        from tkinter import messagebox
                        if len(matches) == 1:
                            chosen = matches[0]
                            if messagebox.askyesno("Possible duplicate", "A book with this title and author already exists without an ISBN. Add this as another physical copy of that record?", parent=self):
                                self.service.create_copy(payload, isbn_override=self.isbn_override.get(), existing_book_id=chosen["id"])
                            else:
                                self.service.create_copy(payload, isbn_override=self.isbn_override.get())
                        else:
                            choice = self._choose_no_isbn_match(matches)
                            if choice == "separate":
                                self.service.create_copy(payload, isbn_override=self.isbn_override.get())
                            elif choice is not None:
                                self.service.create_copy(payload, isbn_override=self.isbn_override.get(), existing_book_id=choice)
                            else:
                                return
                    else:
                        self.service.create_copy(payload, isbn_override=self.isbn_override.get())
                else:
                    self.service.create_copy(payload, isbn_override=self.isbn_override.get())
        self.on_saved()
        self.destroy()
