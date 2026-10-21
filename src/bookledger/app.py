from __future__ import annotations
import csv
import logging
import os
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import shutil
import sqlite3
import sys
import threading
from decimal import Decimal
from calendar import monthrange
from datetime import date
from PIL import Image, ImageTk

from bookledger import __version__
from bookledger.config import APP_NAME, COPY_STATUSES
from bookledger.db.database import Database
from bookledger.paths import AppPaths
from bookledger.config_store import AppConfigStore
from bookledger.services.backups import BackupService
from bookledger.services.catalog import CatalogService, SALE_VOID_REASONS
from bookledger.services.reports import ReportService
from bookledger.services.metadata import GoogleBooksProvider, MetadataLookupService
from bookledger.provider_registry import PROVIDER_REGISTRY, build_providers
from bookledger.provider_settings import ProviderSettings, ProviderSettingsStore
from bookledger.services.photos import PhotoService
from bookledger.services.lifecycle import CopyLifecycleService
from bookledger.services.verification import VerificationService
from bookledger.ui.forms import BookForm
from bookledger.ui.provider_diagnostic import MetadataProviderTestDialog, MetadataProviderTestPanel

try:
    import ttkbootstrap as tb
    _WindowBase = tb.Window
    _HAS_TTKBOOTSTRAP = True
except ImportError:
    _WindowBase = tk.Tk
    _HAS_TTKBOOTSTRAP = False


class BookLedgerApp(_WindowBase):
    def __init__(self):
        if _HAS_TTKBOOTSTRAP:
            super().__init__(themename="flatly")
        else:
            super().__init__()
        self.paths = AppPaths()
        self.paths.prepare()
        self.db = Database(self.paths.database)
        self.paths.migrate_legacy_photos(self.db)
        if (self.paths.legacy_data / "bookledger.sqlite3").exists():
            migration_report = VerificationService(self.db, self.paths.data).verify()
            if not migration_report.ok:
                raise RuntimeError(f"Portable migration verification failed; legacy data was preserved.\n{migration_report.message}")
            self.paths.finalize_legacy_migration()
        self.config_store = AppConfigStore(
            self.paths.provider_config, self.paths.provider_config_fallback()
        )
        self._configuration_warnings = self.config_store.migrate_legacy_settings(
            self.db,
            self.paths.google_books_config,
            self.paths._profile_google_books_config(),
        )
        self.provider_settings_store = ProviderSettingsStore(
            self.paths.provider_config,
            self.paths.provider_config_fallback(),
            config_store=self.config_store,
        )
        self.provider_settings = self.provider_settings_store.load()
        if self._configuration_warnings and not self.provider_settings_store.warning:
            self.provider_settings_store.warning = " ".join(self._configuration_warnings)
        self.catalog = CatalogService(self.db, self.paths.data, config_store=self.config_store)
        self._optional_logger = logging.getLogger("bookledger.optional_diagnostics")
        self._logging_enabled = self._read_logging_enabled()
        self._logging_warning = self._configure_optional_logging(self._logging_enabled) if self._logging_enabled else ""
        if self._logging_enabled and not self._logging_warning:
            self._optional_logger.info("application_started")
        self.reports = ReportService(self.db)
        self.photos = PhotoService(self.paths.photos, self.paths.trash)
        self.lifecycle = CopyLifecycleService(self.db, self.paths.data)
        self.verifier = VerificationService(self.db, self.paths.data)
        self.backups = BackupService(self.db, self.paths.data, self.paths.backups)
        self.metadata_lookup = MetadataLookupService(
            build_providers(self.provider_settings, self._load_google_books_key())
        )
        self.title(f"{APP_NAME} · Book collection manager")
        self.geometry("1280x800")
        self.minsize(1000, 650)
        self._configure_style()
        self._build_shell()
        self.show_page("Dashboard")
        self.bind_all("<Control-n>", lambda _e: self.open_add_form())
        self.bind_all("<Control-f>", lambda _e: self.search_entry.focus_set())
        self.bind_all("<F5>", lambda _e: self.refresh_current())

    def _configure_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Treeview", rowheight=30, font=("Segoe UI", 10), borderwidth=0)
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"), padding=8)
        style.configure("Sidebar.TButton", anchor="w", padding=(14, 11), font=("Segoe UI", 10))
        style.configure("Primary.TButton", padding=(12, 8), font=("Segoe UI", 10, "bold"))
        style.configure("Invalid.TEntry", fieldbackground="#fff0f0")
        style.configure("Invalid.TCombobox", fieldbackground="#fff0f0")

    def _build_shell(self):
        shell = ttk.Frame(self)
        shell.pack(fill="both", expand=True)
        self.sidebar = ttk.Frame(shell, padding=(12, 16), width=210)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        brand = ttk.Frame(self.sidebar)
        brand.pack(fill="x", pady=(0, 24))
        logo_path = self.paths.root / "assets" / "generalists_bookshop_logo.png"
        if logo_path.exists():
            try:
                from PIL import Image, ImageTk
                with Image.open(logo_path) as source:
                    image = source.convert("RGBA")
                    image.thumbnail((176, 66), Image.Resampling.LANCZOS)
                    self._brand_image = ImageTk.PhotoImage(image)
                ttk.Label(brand, image=self._brand_image).pack(anchor="w", pady=(0, 8))
            except Exception:
                self._brand_image = None
        ttk.Label(brand, text="BookLedger", font=("Segoe UI", 17, "bold")).pack(anchor="w")
        ttk.Label(brand, text="Your collection, accounted for", foreground="#64748b", font=("Segoe UI", 9)).pack(anchor="w", pady=(3, 0))
        ttk.Separator(self.sidebar).pack(fill="x", pady=(0, 12))
        self.nav_buttons = {}
        for name, icon in (("Dashboard", "⌂"), ("Catalog", "▤"), ("Inventory", "▦"), ("Acquisitions", "+"), ("Sale History", "↗"), ("Reports", "▥"), ("Settings", "⚙")):
            btn = ttk.Button(self.sidebar, text=f"{icon}   {name}", style="Sidebar.TButton", command=lambda n=name: self.show_page(n))
            btn.pack(fill="x", pady=2)
            self.nav_buttons[name] = btn
        ttk.Frame(self.sidebar).pack(fill="both", expand=True)
        ttk.Label(self.sidebar, text=f"Version {__version__}\nOffline-first · Local data", foreground="#64748b", font=("Segoe UI", 9)).pack(anchor="w", pady=(12, 0))

        right = ttk.Frame(shell, padding=(22, 18))
        right.pack(side="left", fill="both", expand=True)
        header = ttk.Frame(right)
        header.pack(fill="x", pady=(0, 18))
        self.page_title = ttk.Label(header, text="Dashboard", font=("Segoe UI", 22, "bold"))
        self.page_title.pack(side="left")
        self.global_search = tk.StringVar()
        search_frame = ttk.Frame(header)
        search_frame.pack(side="right")
        ttk.Label(search_frame, text="⌕", font=("Segoe UI", 16)).pack(side="left", padx=(0, 5))
        self.search_entry = ttk.Entry(search_frame, textvariable=self.global_search, width=34)
        self.search_entry.pack(side="left")
        self.search_entry.bind("<Return>", lambda _e: self.show_page("Catalog"))
        self.workspace = ttk.Frame(right)
        self.workspace.pack(fill="both", expand=True)
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(right, textvariable=self.status_var, foreground="#64748b", anchor="w").pack(fill="x", pady=(12, 0))

    def _clear_workspace(self):
        # Destroyed page widgets must not remain the active source for a later event.
        self.tree = None
        self.tree_container = None
        self._sales_strike_overlays = []
        for child in self.workspace.winfo_children():
            child.destroy()

    def show_page(self, name):
        if name == "Sales":
            name = "Sale History"
        self.current_page = name
        self.page_title.configure(text=name)
        self._clear_workspace()
        if name in ("Catalog", "Inventory"):
            self._build_catalog_page(inventory=(name == "Inventory"))
        elif name == "Dashboard":
            self._build_dashboard()
        elif name == "Acquisitions":
            self._build_acquisitions()
        elif name == "Sale History":
            self._build_sales()
        elif name == "Reports":
            self._build_reports()
        else:
            self._build_settings()

    def refresh_current(self):
        self.show_page(self.current_page)

    def _build_dashboard(self):
        counts = self.catalog.counts()
        cards = ttk.Frame(self.workspace)
        cards.pack(fill="x", pady=(0, 20))
        metrics = [("Total Copies", counts.get("Total copies", 0)), ("Distinct Titles", counts.get("Distinct Titles", 0)), ("Available", counts.get("Available", 0)), ("Listed", counts.get("Listed", 0)), ("Not for Sale", counts.get("Not for Sale", 0)), ("Sold", counts.get("Sold", 0))]
        for idx, (label, value) in enumerate(metrics):
            card = ttk.LabelFrame(cards, text=label, padding=16)
            card.grid(row=idx // 3, column=idx % 3, sticky="nsew", padx=(0, 12), pady=(0, 12))
            ttk.Label(card, text=str(value), font=("Segoe UI", 25, "bold")).pack(anchor="w")
            cards.grid_columnconfigure(idx % 3, weight=1)
        actions = ttk.LabelFrame(self.workspace, text="Quick actions", padding=16)
        actions.pack(fill="x", pady=(0, 18))
        ttk.Button(actions, text="＋  Add a book", style="Primary.TButton", command=self.open_add_form).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Open catalog", command=lambda: self.show_page("Catalog")).pack(side="left", padx=8)
        ttk.Button(actions, text="Back up now", command=self.create_backup).pack(side="left", padx=8)
        recent = ttk.LabelFrame(self.workspace, text="Recently added copies", padding=12)
        recent.pack(fill="both", expand=True)
        self._make_tree(recent, columns=("code", "title", "author", "status", "price"), headings=("Copy ID", "Title", "Author", "Status", "Price"), height=8)
        rows = self.catalog.list_copies()
        for row in sorted(rows, key=lambda r: r["copy_id"], reverse=True)[:8]:
            self.tree.insert("", "end", iid=str(row["copy_id"]), values=(row["copy_code"], row["title"], row["author"], row["status"], self.money(row["display_price_minor"])))
        self.tree.bind("<Double-1>", self._on_tree_double_click)

    def _build_catalog_page(self, inventory=False):
        self._catalog_inventory = inventory
        top = ttk.Frame(self.workspace)
        top.pack(fill="x", pady=(0, 12))
        ttk.Label(top, text="Manage physical copies" if inventory else "Browse physical copies", foreground="#64748b").pack(side="left")
        ttk.Button(top, text="＋ Add Book", style="Primary.TButton", command=self.open_add_form).pack(side="right")
        filters = ttk.Frame(self.workspace)
        filters.pack(fill="x", pady=(0, 12))
        self.genre_filter = tk.StringVar(value="All")
        self.condition_filter = tk.StringVar(value="All")
        self.location_filter = tk.StringVar(value="All")
        self.status_filter = tk.StringVar(value="All")
        locations = self.catalog.list_locations()
        filter_specs = (
            ("Genre", self.genre_filter, ("All",) + self.catalog.list_genres(), 20),
            ("Condition", self.condition_filter, ("All", "Like New", "Very Good", "Good", "Acceptable", "Poor"), 13),
            ("Location", self.location_filter, ("All",) + locations, 14),
            ("Status", self.status_filter, ("All",) + COPY_STATUSES, 13),
        )
        for label, variable, values, width in filter_specs:
            ttk.Label(filters, text=label).pack(side="left", padx=(0, 5))
            combo = ttk.Combobox(filters, textvariable=variable, values=values, state="readonly", width=width)
            combo.pack(side="left", padx=(0, 10))
            combo.bind("<<ComboboxSelected>>", lambda _event: self._populate_catalog())
        ttk.Button(filters, text="Clear", command=self._clear_filters).pack(side="left")
        frame = ttk.Frame(self.workspace)
        frame.pack(fill="both", expand=True)
        if inventory:
            ttk.Button(top, text="Edit Selected", command=self.open_selected_edit).pack(side="right", padx=(0, 8))
            self._make_tree(frame, columns=("code", "copy_number", "title", "author", "format", "condition", "location", "price", "status"), headings=("Copy ID", "Copy #", "Title", "Author", "Format", "Condition", "Location", "Price (PHP)", "Status"), height=18)
            self.tree.bind("<Double-1>", self._on_tree_double_click)
            self.tree.bind("<Button-3>", self._on_inventory_right_click)
            for col in self.tree["columns"]:
                self.tree.heading(col, command=lambda c=col: self._sort_inventory(c))
        else:
            sort_bar = ttk.Frame(frame)
            sort_bar.pack(fill="x", pady=(0, 8))
            ttk.Label(sort_bar, text="Sort by").pack(side="left")
            self.catalog_sort = tk.StringVar(value=getattr(self, "_catalog_sort_value", "Title"))
            sort_box = ttk.Combobox(sort_bar, textvariable=self.catalog_sort, values=("Title", "Price: Low to High", "Price: High to Low", "Copy ID: Newest"), state="readonly", width=22)
            sort_box.pack(side="left", padx=(6, 0))
            sort_box.bind("<<ComboboxSelected>>", self._catalog_sort_changed)
            self._build_catalog_grid(frame)
        self._populate_catalog()

    def _make_tree(self, parent, *, columns, headings, height=15):
        container = ttk.Frame(parent)
        self.tree_container = container
        container.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(container, columns=columns, show="headings", height=height, selectmode="browse")
        widths = {"code": 110, "copy_number": 78, "title": 240, "author": 180, "genre": 130, "status": 115, "price": 110, "location": 130}
        for col, heading in zip(columns, headings):
            self.tree.heading(col, text=heading)
            self.tree.column(col, width=widths.get(col, 130), minwidth=75, stretch=True)
        ybar = ttk.Scrollbar(container, orient="vertical", command=self.tree.yview)
        xbar = ttk.Scrollbar(container, orient="horizontal", command=self.tree.xview)
        def set_vertical_scroll(first, last):
            ybar.set(first, last)
            if getattr(self, "current_page", None) == "Sale History":
                self.after_idle(self._refresh_sale_strikethroughs)
        self.tree.configure(yscrollcommand=set_vertical_scroll, xscrollcommand=xbar.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        ybar.grid(row=0, column=1, sticky="ns")
        xbar.grid(row=1, column=0, sticky="ew")
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)
        if getattr(self, "current_page", None) == "Sale History":
            self.tree.bind("<Configure>", lambda _event: self.after_idle(self._refresh_sale_strikethroughs), add="+")

    def _populate_catalog(self):
        rows = self.catalog.list_copies(
            self.global_search.get(), self.status_filter.get(), self.genre_filter.get(),
            self.condition_filter.get(), self.location_filter.get(),
        )
        if self._catalog_inventory:
            if not hasattr(self, "tree") or not self.tree.winfo_exists():
                return
            sort_column = getattr(self, "_inventory_sort_column", "title")
            reverse = getattr(self, "_inventory_sort_reverse", False)
            value_key = {"code": "copy_code", "copy_number": "copy_number", "title": "title", "author": "author", "format": "format", "condition": "condition", "location": "location", "price": "display_price_minor", "status": "status"}.get(sort_column, "title")
            rows = self._sold_last_sort(rows, lambda row: row[value_key] or "", reverse)
            self._visible_rows = rows
            self.tree.delete(*self.tree.get_children())
            for row in rows:
                values = (row["copy_code"], row["copy_number"], row["title"], row["author"], row["format"], row["condition"], row["location"], self.money(row["display_price_minor"]), row["status"])
                self.tree.insert("", "end", iid=str(row["copy_id"]), values=values)
        else:
            rows = self._sort_catalog_rows(rows)
            self._visible_rows = rows
            self._render_catalog_cards(rows)
        self.status_var.set(f"{len(rows)} physical copy/copies shown")

    def _build_catalog_grid(self, parent):
        self.catalog_canvas = tk.Canvas(parent, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=self.catalog_canvas.yview)
        self.catalog_canvas.configure(yscrollcommand=scrollbar.set)
        self.catalog_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.catalog_cards = ttk.Frame(self.catalog_canvas)
        self._catalog_window = self.catalog_canvas.create_window((0, 0), window=self.catalog_cards, anchor="nw")
        self.catalog_cards.bind("<Configure>", lambda _event: self.catalog_canvas.configure(scrollregion=self.catalog_canvas.bbox("all")))
        self.catalog_canvas.bind("<Configure>", lambda event: self.catalog_canvas.itemconfigure(self._catalog_window, width=event.width))

    def _render_catalog_cards(self, rows):
        for child in self.catalog_cards.winfo_children():
            child.destroy()
        self._catalog_images = []
        width = max(self.catalog_canvas.winfo_width(), 760)
        columns = max(2, min(6, width // 195))
        for col in range(columns):
            self.catalog_cards.grid_columnconfigure(col, weight=1, uniform="catalog-card")
        for index, row in enumerate(rows):
            card = ttk.LabelFrame(self.catalog_cards, text=row["copy_code"], padding=8)
            card.grid(row=index // columns, column=index % columns, sticky="nsew", padx=7, pady=7)
            art = tk.Frame(card, width=150, height=170, background="#edf1f5")
            art.pack(fill="x", pady=(0, 7))
            art.pack_propagate(False)
            photo_path = Path(row["photo_path"])
            if not photo_path.is_absolute():
                photo_path = self.paths.data / photo_path
            try:
                with Image.open(photo_path) as source:
                    image = source.convert("RGB")
                    image.thumbnail((145, 165), Image.Resampling.LANCZOS)
                    image = self._sold_thumbnail(image, row["status"])
                    photo = ImageTk.PhotoImage(image)
                self._catalog_images.append(photo)
                image_label = tk.Label(art, image=photo, background="#edf1f5")
                image_label.place(relx=0.5, rely=0.5, anchor="center")
            except (OSError, tk.TclError):
                tk.Label(art, text="Photo Unavailable", background="#edf1f5", foreground="#596579").place(relx=0.5, rely=0.5, anchor="center")
            if row["status"] == "Sold":
                tk.Label(art, text="SOLD", bg="#b42318", fg="white", font=("Segoe UI", 12, "bold"), padx=10, pady=4).place(relx=0.5, rely=0.5, anchor="center")
            ttk.Label(card, text=row["title"], font=("Segoe UI", 10, "bold"), wraplength=165).pack(anchor="w")
            ttk.Label(card, text=self._physical_copy_label(row), foreground="#596579").pack(anchor="w", pady=(2, 0))
            ttk.Label(card, text=row["author"], foreground="#64748b", wraplength=165).pack(anchor="w", pady=(2, 5))
            ttk.Label(card, text=self.money(row["display_price_minor"]), font=("Segoe UI", 11, "bold")).pack(anchor="w")
            def bind_card(widget, copy_id=row["copy_id"]):
                widget.bind("<Double-Button-1>", lambda _event: self.open_copy_details(copy_id))
                widget.bind("<Button-3>", lambda event: self.show_copy_context_menu(copy_id, event.x_root, event.y_root))
                for child in widget.winfo_children():
                    bind_card(child, copy_id)
            bind_card(card)

    def _sort_inventory(self, column):
        if getattr(self, "_inventory_sort_column", None) == column:
            self._inventory_sort_reverse = not getattr(self, "_inventory_sort_reverse", False)
        else:
            self._inventory_sort_column = column
            self._inventory_sort_reverse = False
        value_key = {"code": "copy_code", "copy_number": "copy_number", "title": "title", "author": "author", "format": "format", "condition": "condition", "location": "location", "price": "display_price_minor", "status": "status"}[column]
        self._visible_rows = self._sold_last_sort(self._visible_rows, lambda row: row[value_key] or "", self._inventory_sort_reverse)
        for index, row in enumerate(self._visible_rows):
            values = (row["copy_code"], row["copy_number"], row["title"], row["author"], row["format"], row["condition"], row["location"], self.money(row["display_price_minor"]), row["status"])
            self.tree.item(str(row["copy_id"]), values=values)
            self.tree.move(str(row["copy_id"]), "", index)

    @staticmethod
    def _sold_last_sort(rows, key, reverse=False):
        in_stock = [row for row in rows if row["status"] != "Sold"]
        sold = [row for row in rows if row["status"] == "Sold"]
        return sorted(in_stock, key=key, reverse=reverse) + sorted(sold, key=key, reverse=reverse)

    @staticmethod
    def _sold_thumbnail(image, status):
        if status != "Sold":
            return image
        gray_overlay = Image.new("RGB", image.size, "#9ca3af")
        return Image.blend(image, gray_overlay, 0.48)

    @staticmethod
    def _physical_copy_label(row):
        return f"Copy {row['copy_number']}"

    def _sort_catalog_rows(self, rows):
        choice = self.catalog_sort.get()
        if choice == "Price: Low to High":
            return self._sold_last_sort(rows, lambda row: row["display_price_minor"])
        if choice == "Price: High to Low":
            return self._sold_last_sort(rows, lambda row: row["display_price_minor"], True)
        if choice == "Copy ID: Newest":
            return self._sold_last_sort(rows, lambda row: row["copy_id"], True)
        return self._sold_last_sort(rows, lambda row: (row["title"].casefold(), row["copy_number"]))

    def _catalog_sort_changed(self, _event=None):
        self._catalog_sort_value = self.catalog_sort.get()
        self._populate_catalog()

    def _on_tree_double_click(self, event):
        """Open the row activated in the currently displayed Treeview."""
        tree = event.widget
        if tree is not getattr(self, "tree", None):
            return "break"
        if getattr(self, "current_page", None) == "Sale History":
            try:
                item = tree.identify_row(event.y)
                sale = next((row for row in getattr(self, "_sales_rows", ()) if str(row["sale_id"]) == item), None)
            except (tk.TclError, KeyError):
                sale = None
            if sale:
                self.open_copy_details(int(sale["copy_id"]))
            return "break"
        if getattr(self, "current_page", None) == "Sales":
            return "break"
        try:
            if not tree.winfo_exists():
                return "break"
            clicked_item = tree.identify_row(event.y)
            if not clicked_item or clicked_item not in tree.selection():
                return "break"
        except tk.TclError:
            # A deferred event can race with page teardown. Ignore only when the
            # originating widget has been destroyed, not arbitrary callback errors.
            return "break"
        copy_id = int(clicked_item)
        self.open_selected_edit(copy_id)
        return "break"

    def _on_inventory_right_click(self, event):
        tree = event.widget
        if tree is not getattr(self, "tree", None) or self.current_page != "Inventory":
            return "break"
        try:
            if not tree.winfo_exists():
                return "break"
            item = tree.identify_row(event.y)
            if not item:
                return "break"
            tree.selection_set(item)
            tree.focus(item)
        except tk.TclError:
            return "break"
        self.show_copy_context_menu(int(item), event.x_root, event.y_root)
        return "break"

    def show_copy_context_menu(self, copy_id, x_root, y_root):
        row = self.catalog.get_copy(int(copy_id))
        if not row:
            self.status_var.set("That copy could not be found. Refresh and try again.")
            return
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="View Details", command=lambda cid=copy_id: self.open_copy_details(cid))
        menu.add_command(label="Create Poster", command=self._poster_not_implemented)
        for status in ("Available", "Listed", "Not for Sale", "Sold"):
            menu.add_command(
                label=f"Mark as {status}",
                state="disabled" if row["status"] == status else "normal",
                command=lambda target=status, cid=copy_id: self._change_copy_status(cid, target),
            )
        menu.add_command(label="Edit Book", command=lambda cid=copy_id: self.open_selected_edit(cid))
        menu.add_command(label="Delete Book", command=lambda cid=copy_id: self._confirm_delete(cid))
        try:
            menu.tk_popup(x_root, y_root)
        finally:
            menu.grab_release()

    def _poster_not_implemented(self):
        messagebox.showinfo("Create Poster", "Not implemented yet.", parent=self)

    def _change_copy_status(self, copy_id, target_status):
        row = self.catalog.get_copy(int(copy_id))
        if not row:
            self.status_var.set("That copy could not be found. Refresh and try again.")
            return
        current = row["status"]
        if current == target_status:
            return
        void_reason = None
        if self.catalog.status_change_requires_confirmation(current, target_status):
            if current == "Sold":
                void_reason = self._ask_sale_void_reason(row, target_status)
                if void_reason is None:
                    return
            else:
                prompt = f"Mark {row['copy_code']} ({row['title']}) as {target_status}?"
                if not messagebox.askyesno("Confirm Status Change", prompt, parent=self):
                    return
        try:
            if void_reason is None:
                self.catalog.change_status(int(copy_id), target_status)
            else:
                self.catalog.change_status(int(copy_id), target_status, void_reason=void_reason)
        except (ValueError, KeyError, sqlite3.DatabaseError) as exc:
            messagebox.showerror("Status Change Failed", str(exc), parent=self)
            return
        self._after_save(f"{row['copy_code']} marked {target_status}.")

    def _ask_sale_void_reason(self, row, target_status):
        dialog = tk.Toplevel(self)
        dialog.title("Void Sale and Change Status")
        dialog.transient(self)
        dialog.resizable(False, False)
        result = {"reason": None}
        frame = ttk.Frame(dialog, padding=18)
        frame.pack(fill="both", expand=True)
        ttk.Label(
            frame,
            text=(f"Changing {row['copy_code']} ({row['title']}) from Sold to {target_status} will void this sale, "
                  "exclude it from revenue calculations, and retain it in Sale History."),
            wraplength=440,
            justify="left",
        ).pack(anchor="w", pady=(0, 12))
        ttk.Label(frame, text="Reason for Voiding Sale").pack(anchor="w")
        reason = tk.StringVar(value="")
        choices = ttk.Combobox(frame, textvariable=reason, values=SALE_VOID_REASONS, state="readonly", width=38)
        choices.pack(fill="x", pady=(4, 16))
        buttons = ttk.Frame(frame)
        buttons.pack(fill="x")
        def cancel():
            result["reason"] = None
            dialog.destroy()
        def confirm():
            selected = reason.get()
            if selected in SALE_VOID_REASONS:
                result["reason"] = selected
                dialog.destroy()
        confirm_button = ttk.Button(buttons, text="Confirm", command=confirm)
        confirm_button.configure(state="disabled")
        choices.bind("<<ComboboxSelected>>", lambda _event: confirm_button.configure(state="normal" if reason.get() in SALE_VOID_REASONS else "disabled"))
        ttk.Button(buttons, text="Cancel", command=cancel).pack(side="right")
        confirm_button.pack(side="right", padx=(0, 8))
        dialog.protocol("WM_DELETE_WINDOW", cancel)
        dialog.grab_set()
        choices.focus_set()
        self.wait_window(dialog)
        return result["reason"]

    def _confirm_delete(self, copy_id):
        row = self.catalog.get_copy(int(copy_id))
        if not row:
            self.status_var.set("That copy could not be found. Refresh and try again.")
            return
        confirmed = messagebox.askyesno(
            "Delete Book",
            f"Delete physical copy {row['copy_code']} — {row['title']}?",
            parent=self,
        )
        if confirmed:
            try:
                self.lifecycle.trash_copy(int(copy_id))
                self._after_save(f"{row['copy_code']} moved to Trash.")
            except Exception as exc:
                messagebox.showerror("Delete Failed", f"The copy was not safely moved to Trash: {exc}", parent=self)

    def _clear_filters(self):
        self.global_search.set("")
        self.status_filter.set("All")
        self.genre_filter.set("All")
        self.condition_filter.set("All")
        self.location_filter.set("All")
        self._populate_catalog()

    def _build_acquisitions(self):
        panel = ttk.LabelFrame(self.workspace, text="Catalog intake", padding=22)
        panel.pack(fill="x", anchor="n")
        ttk.Label(panel, text="Add one physical copy at a time, with a dedicated photo and its own valuation.", wraplength=700).pack(anchor="w", pady=(0, 14))
        ttk.Button(panel, text="＋  Add a book", style="Primary.TButton", command=self.open_add_form).pack(anchor="w")
        ttk.Label(panel, text="Tip: use Ctrl+N from anywhere in BookLedger to start intake.", foreground="#64748b").pack(anchor="w", pady=(14, 0))
        duplicate = ttk.LabelFrame(self.workspace, text="Intake rules", padding=16)
        duplicate.pack(fill="x", pady=18)
        for line in ("ISBN is optional; ISBN-10/13 check digits are validated with manual override.",
                     "The seven required inputs must be valid before a copy can be saved.",
                     "Metadata categories outside your approved genre list must be recategorized.",
                     "Photos are compressed and stored in the portable BookLedger data folder."):
            ttk.Label(duplicate, text=f"•  {line}").pack(anchor="w", pady=3)

    def _build_sales(self):
        top = ttk.Frame(self.workspace)
        top.pack(fill="x", pady=(0, 12))
        self._sales_rows = self.catalog.list_sales()
        self._sales_sort_column = None
        self._sales_sort_state = 0
        revenue = self.reports.sales_revenue()
        ttk.Label(top, text=f"Sale History · Revenue {self.money(revenue)}", foreground="#64748b", font=("Segoe UI", 12, "bold")).pack(side="left")
        frame = ttk.Frame(self.workspace)
        frame.pack(fill="both", expand=True)
        self._make_tree(frame, columns=("code", "title", "author", "sale_date", "sale_price"), headings=("Copy ID", "Title", "Author", "Date Sold", "Price"), height=18)
        self._configure_sale_history_tree_styles()
        for col, label in zip(self.tree["columns"], ("Copy ID", "Title", "Author", "Date Sold", "Price")):
            self.tree.heading(col, text=label, command=lambda column=col: self._sort_sales(column))
        self._render_sales_rows(self._default_sales_order(self._sales_rows))
        self.tree.bind("<Double-1>", self._on_tree_double_click)
        self.after_idle(self._refresh_sale_strikethroughs)
        if not self._sales_rows:
            self.status_var.set("No sales recorded yet")

    def _configure_sale_history_tree_styles(self):
        self.tree.tag_configure("voided_sale", foreground="#858585", font=("Segoe UI", 10, "overstrike"))

    @staticmethod
    def _default_sales_order(rows):
        return sorted(rows, key=lambda row: (int(row["copy_id"]), int(row["sale_id"])))

    @staticmethod
    def _sales_sort_key(column, row):
        if column == "code":
            return str(row["copy_code"]).casefold()
        if column == "title":
            return str(row["title"]).casefold()
        if column == "author":
            return str(row["author"]).casefold()
        if column == "sale_date":
            return str(row["sale_date"])
        if column == "sale_price":
            return int(row["price_minor"])
        raise KeyError(column)

    def _render_sales_rows(self, rows):
        existing = set(self.tree.get_children())
        for row in rows:
            item = str(row["sale_id"])
            if item not in existing:
                tags = ("voided_sale",) if row.get("voided_at") else ()
                self.tree.insert("", "end", iid=item, values=(row["copy_code"], row["title"], row["author"], row["sale_date"], self.money(row["price_minor"])), tags=tags)
        # One Treeview command reorders the already-loaded rows without rebuilding
        # the widget or issuing one Tcl round-trip per sale.
        self.tree.set_children("", *(str(row["sale_id"]) for row in rows))

    def _refresh_sale_strikethroughs(self):
        if getattr(self, "current_page", None) != "Sale History":
            return
        tree = getattr(self, "tree", None)
        container = getattr(self, "tree_container", None)
        if tree is None or container is None:
            return
        try:
            if not tree.winfo_exists() or not container.winfo_exists():
                return
            for overlay in getattr(self, "_sales_strike_overlays", ()):
                if overlay.winfo_exists():
                    overlay.destroy()
        except tk.TclError:
            return
        self._sales_strike_overlays = []
        background = ttk.Style(self).lookup("Treeview", "background") or "#ffffff"
        for row in getattr(self, "_sales_rows", ()):
            if not row.get("voided_at"):
                continue
            bounds = tree.bbox(str(row["sale_id"]))
            if not bounds:
                continue
            x, y, width, row_height = bounds
            if width <= 0 or row_height <= 0:
                continue
            overlay = tk.Canvas(container, width=width, height=2, background=background, bd=0, highlightthickness=0)
            overlay.create_line(0, 1, width, 1, fill="#c62828", width=1)
            overlay.place(x=x, y=y + row_height // 2, width=width, height=2)
            for sequence in ("<Button-1>", "<ButtonRelease-1>", "<Double-Button-1>", "<Button-3>", "<MouseWheel>"):
                overlay.bind(sequence, lambda event, seq=sequence: self._forward_tree_overlay_event(event, seq))
            self._sales_strike_overlays.append(overlay)

    def _forward_tree_overlay_event(self, event, sequence):
        tree = self.tree
        if tree is None or not tree.winfo_exists():
            return "break"
        options = {
            "x": event.x_root - tree.winfo_rootx(),
            "y": event.y_root - tree.winfo_rooty(),
            "state": event.state,
        }
        if sequence == "<MouseWheel>":
            options["delta"] = event.delta
        tree.event_generate(sequence, **options)
        return "break"

    def _sort_sales(self, column):
        if self._sales_sort_column != column:
            self._sales_sort_column, self._sales_sort_state = column, 1
            ordered = sorted(self._sales_rows, key=lambda row: self._sales_sort_key(column, row), reverse=True)
        elif self._sales_sort_state == 1:
            self._sales_sort_state = 2
            ordered = sorted(self._sales_rows, key=lambda row: self._sales_sort_key(column, row))
        else:
            self._sales_sort_column, self._sales_sort_state = None, 0
            ordered = self._default_sales_order(self._sales_rows)
        labels = {"code": "Copy ID", "title": "Title", "author": "Author", "sale_date": "Date Sold", "sale_price": "Price"}
        for col, label in labels.items():
            arrow = " ↓" if col == self._sales_sort_column and self._sales_sort_state == 1 else " ↑" if col == self._sales_sort_column else ""
            self.tree.heading(col, text=label + arrow)
        self._render_sales_rows(ordered)

    def _build_reports(self):
        counts = self.catalog.counts()
        summary = ttk.LabelFrame(self.workspace, text="Inventory Summary", padding=12)
        summary.pack(fill="x", anchor="n")
        summary_labels = ("Total copies", "Distinct Titles", *COPY_STATUSES)
        for index, label in enumerate(summary_labels):
            ttk.Label(summary, text=label, width=18).grid(row=0, column=index, sticky="w", padx=(0, 6))
            ttk.Label(summary, text=str(counts.get(label, 0)), font=("Segoe UI", 11, "bold")).grid(row=1, column=index, sticky="w", padx=(0, 6), pady=(4, 0))
            summary.grid_columnconfigure(index, weight=1)

        values = self.reports.inventory_valuation()
        valuation = ttk.LabelFrame(self.workspace, text="Inventory Valuation", padding=12)
        valuation.pack(fill="x", pady=(10, 0))
        for index, (label, key) in enumerate((
            ("Total Library Value", "total_library_value"),
            ("Expected Revenue", "expected_revenue"),
            ("Sales Revenue", "sales_revenue"),
        )):
            card = ttk.Frame(valuation)
            card.grid(row=0, column=index, sticky="ew", padx=(0, 16))
            ttk.Label(card, text=label, foreground="#64748b").pack(anchor="w")
            ttk.Label(card, text=self.money(values[key]), font=("Segoe UI", 17, "bold")).pack(anchor="w", pady=(3, 0))
            valuation.grid_columnconfigure(index, weight=1)

        charts = ttk.Frame(self.workspace)
        charts.pack(fill="both", expand=True, pady=(10, 0))
        charts.grid_columnconfigure(0, weight=3, uniform="report-chart")
        charts.grid_columnconfigure(1, weight=2, uniform="report-chart")
        charts.grid_rowconfigure(0, weight=1)
        self._build_monthly_revenue_chart(charts)
        self._build_genre_chart(charts)

    @staticmethod
    def _month_shift(value: date, amount: int) -> date:
        month_index = value.year * 12 + value.month - 1 + amount
        return date(month_index // 12, month_index % 12 + 1, 1)

    def _build_monthly_revenue_chart(self, parent):
        panel = ttk.LabelFrame(parent, text="Monthly Revenue", padding=10)
        panel.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self._report_today = date.today().replace(day=1)
        earliest = self.reports.earliest_recorded_book_date()
        self._report_earliest_month = earliest.replace(day=1) if earliest else None
        self._report_month = self._report_today
        if self._report_earliest_month and self._report_earliest_month > self._report_today:
            self._report_month = self._report_earliest_month
        nav = ttk.Frame(panel)
        nav.pack(fill="x", pady=(0, 6))
        self._report_prev = ttk.Button(nav, text="Previous", command=lambda: self._move_report_month(-1))
        self._report_prev.pack(side="left")
        self._report_month_label = ttk.Label(nav, text="", font=("Segoe UI", 13, "bold"), anchor="center")
        self._report_month_label.pack(side="left", fill="x", expand=True, padx=8)
        self._report_next = ttk.Button(nav, text="Next", command=lambda: self._move_report_month(1))
        self._report_next.pack(side="right")
        self._revenue_empty = ttk.Label(panel, text="No sales data for this month", foreground="#64748b", anchor="center")
        self._revenue_canvas = tk.Canvas(panel, highlightthickness=0, height=245)
        self._revenue_canvas.pack(fill="both", expand=True)
        self._revenue_canvas.bind("<Configure>", lambda _event: self._draw_monthly_revenue())
        self._update_monthly_revenue()

    def _move_report_month(self, amount):
        if self._report_earliest_month is None:
            return
        target = self._month_shift(self._report_month, amount)
        if self._report_earliest_month and target < self._report_earliest_month:
            target = self._report_earliest_month
        if target > self._report_today:
            target = self._report_today
        if target != self._report_month:
            self._report_month = target
            self._update_monthly_revenue()

    def _update_monthly_revenue(self):
        self._report_month_label.configure(text=self._report_month.strftime("%B %Y"))
        self._report_prev.configure(state="disabled" if self._report_earliest_month is None or self._report_month <= self._report_earliest_month else "normal")
        self._report_next.configure(state="disabled" if self._report_month >= self._report_today else "normal")
        self._monthly_revenue = self.reports.monthly_revenue(self._report_month.year, self._report_month.month)
        if self._monthly_revenue:
            self._revenue_empty.pack_forget()
            self._revenue_canvas.pack(fill="both", expand=True)
            self._draw_monthly_revenue()
        else:
            self._revenue_canvas.delete("all")
            self._revenue_canvas.pack_forget()
            self._revenue_empty.pack(fill="both", expand=True, pady=25)

    def _draw_monthly_revenue(self):
        if not getattr(self, "_monthly_revenue", None) or not self._revenue_canvas.winfo_exists():
            return
        canvas = self._revenue_canvas
        width, height = max(canvas.winfo_width(), 300), max(canvas.winfo_height(), 190)
        canvas.delete("all")
        left, right, top, bottom = 64, width - 14, 18, height - 42
        if right <= left or bottom <= top:
            return
        days = monthrange(self._report_month.year, self._report_month.month)[1]
        max_value = max(self._monthly_revenue.values())
        scale = max_value or 1
        for tick in range(5):
            y = bottom - (bottom - top) * tick / 4
            amount = int(round(scale * tick / 4))
            canvas.create_line(left, y, right, y, fill="#d7dee7")
            canvas.create_text(left - 7, y, text=self.money(amount), anchor="e", fill="#596579", font=("Segoe UI", 8))
        slot = (right - left) / days
        bar_width = max(2, min(16, slot * .68))
        for day, value in self._monthly_revenue.items():
            x = left + (day - .5) * slot
            y = bottom - (bottom - top) * value / scale
            canvas.create_rectangle(x - bar_width / 2, y, x + bar_width / 2, bottom, fill="#3b82f6", outline="")
        for day in sorted(set([1, 5, 10, 15, 20, 25, days])):
            x = left + (day - .5) * slot
            canvas.create_text(x, bottom + 15, text=str(day), fill="#596579", font=("Segoe UI", 8))
        canvas.create_text((left + right) / 2, height - 10, text="Day", fill="#334155", font=("Segoe UI", 9, "bold"))
        canvas.create_text(12, (top + bottom) / 2, text="Revenue (PHP)", angle=90, fill="#334155", font=("Segoe UI", 9, "bold"))

    def _build_genre_chart(self, parent):
        panel = ttk.LabelFrame(parent, text="Books by Genre", padding=10)
        panel.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        self._genre_rows = self.reports.books_by_genre()
        if not self._genre_rows:
            ttk.Label(panel, text="No inventory data", foreground="#64748b", anchor="center").pack(fill="both", expand=True, pady=25)
            return
        chart_frame = ttk.Frame(panel)
        chart_frame.pack(fill="both", expand=True)
        canvas = tk.Canvas(chart_frame, highlightthickness=0, height=245)
        scroll = ttk.Scrollbar(chart_frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        canvas.bind("<Configure>", lambda _event: self._draw_genre_chart(canvas))
        self._genre_canvas = canvas
        self._draw_genre_chart(canvas)

    def _draw_genre_chart(self, canvas):
        if not self._genre_rows or not canvas.winfo_exists():
            return
        width = max(canvas.winfo_width(), 280)
        label_margin = min(max(max(len(row["genre"]) for row in self._genre_rows) * 7 + 12, 90), width * .55)
        plot_left, plot_right = label_margin, width - 28
        row_height, top, axis_height = 36, 18, 30
        height = top + len(self._genre_rows) * row_height + axis_height
        canvas.delete("all")
        max_count = max(row["copy_count"] for row in self._genre_rows)
        for index, row in enumerate(self._genre_rows):
            y = top + index * row_height
            canvas.create_text(plot_left - 8, y + 10, text=row["genre"], width=max(label_margin - 12, 40), justify="right", anchor="e", fill="#334155", font=("Segoe UI", 9))
            bar_end = plot_left + (plot_right - plot_left) * row["copy_count"] / max_count
            canvas.create_rectangle(plot_left, y + 2, bar_end, y + 18, fill="#14a085", outline="")
            canvas.create_text(bar_end + 4, y + 10, text=str(row["copy_count"]), anchor="w", fill="#334155", font=("Segoe UI", 8))
        canvas.create_line(plot_left, height - axis_height, plot_right, height - axis_height, fill="#64748b")
        step = max(1, (max_count + 3) // 4)
        ticks = list(range(0, max_count, step)) + [max_count]
        for tick in sorted(set(ticks)):
            x = plot_left + (plot_right - plot_left) * tick / max_count
            canvas.create_line(x, top, x, height - axis_height, fill="#e2e8f0")
            canvas.create_text(x, height - axis_height + 9, text=str(tick), fill="#596579", font=("Segoe UI", 8))
        canvas.create_text((plot_left + plot_right) / 2, height - 5, text="Count", fill="#334155", font=("Segoe UI", 9, "bold"))
        canvas.create_text(12, top + len(self._genre_rows) * row_height / 2, text="Genre", angle=90, fill="#334155", font=("Segoe UI", 9, "bold"))
        canvas.configure(scrollregion=(0, 0, width, height))

    def _build_settings(self):
        notebook = ttk.Notebook(self.workspace)
        notebook.pack(fill="both", expand=True)
        self.settings_notebook = notebook
        tabs = {}
        for name in (
            "Mobile App Setup",
            "Metadata Sources",
            "API Management",
            "Storage and Backup",
            "Poster Setup",
            "Preferences",
        ):
            tab = ttk.Frame(notebook, padding=12)
            notebook.add(tab, text=name)
            tabs[name] = tab

        self._build_mobile_app_setup(tabs["Mobile App Setup"])
        self._build_metadata_sources(tabs["Metadata Sources"])
        self._build_api_management(tabs["API Management"])
        self._build_storage_settings(tabs["Storage and Backup"])
        self._build_poster_setup(tabs["Poster Setup"])
        self._build_preferences(tabs["Preferences"])

    def _build_mobile_app_setup(self, parent):
        ttk.Label(
            parent,
            text="Mobile app setup is reserved for future development.",
            foreground="#64748b",
        ).pack(anchor="nw")

    def _build_metadata_sources(self, parent):
        parent.columnconfigure(0, weight=3, uniform="metadata")
        parent.columnconfigure(1, weight=2, uniform="metadata")
        parent.rowconfigure(0, weight=1)

        panel = ttk.LabelFrame(parent, text="Metadata Sources", padding=12)
        panel.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        ttk.Label(panel, text="Enabled sources are searched from top to bottom. Drag a source by its handle to change priority.", wraplength=560).pack(anchor="w")
        self._provider_rows = {}
        self._provider_variables = {}
        rows = ttk.Frame(panel)
        rows.pack(fill="x", pady=(8, 4))
        for descriptor in PROVIDER_REGISTRY:
            if not descriptor.implemented:
                continue
            row = ttk.Frame(rows, padding=(4, 3))
            row.pack(fill="x")
            var = tk.BooleanVar(value=self.provider_settings.enabled.get(descriptor.id, True))
            ttk.Checkbutton(row, variable=var).pack(side="left")
            name = ttk.Label(row, text=descriptor.name, width=24, anchor="w")
            name.pack(side="left")
            ttk.Label(row, text="Implemented" if descriptor.implemented else "Planned · unavailable", foreground="#64748b").pack(side="left", padx=(6, 0))
            handle = ttk.Label(row, text="⠿", cursor="fleur", foreground="#64748b", padding=(12, 0))
            handle.pack(side="right")
            for widget in (row, name, handle):
                widget.bind("<ButtonPress-1>", lambda event, key=descriptor.id: self._provider_drag_start(event, key))
                widget.bind("<B1-Motion>", self._provider_drag_motion)
                widget.bind("<ButtonRelease-1>", self._provider_drag_end)
            self._provider_rows[descriptor.id] = row
            self._provider_variables[descriptor.id] = var
        self._reorder_provider_rows(self.provider_settings.order)
        controls = ttk.Frame(panel)
        controls.pack(fill="x", pady=(6, 0))
        ttk.Button(controls, text="Save Metadata Sources", command=self._save_provider_settings).pack(side="left")
        ttk.Button(controls, text="Restore Defaults", command=self._restore_provider_defaults).pack(side="left", padx=8)
        warning = self.provider_settings_store.warning or ""
        config_path = self.provider_settings_store.active_path
        self._provider_config_status = tk.StringVar(value=warning or f"Settings file: {config_path}")
        ttk.Label(panel, textvariable=self._provider_config_status, foreground="#64748b", wraplength=560).pack(anchor="w", pady=(8, 0))

        planned = ttk.LabelFrame(parent, text="Planned metadata integrations", padding=16)
        planned.grid(row=1, column=0, sticky="ew", padx=(0, 8), pady=(8, 0))
        for name in ("ISBNdb", "WorldCat", "Internet Archive", "BigBook", "Hardcover", "Goodreads"):
            ttk.Label(planned, text=f"{name} — planned; not integrated.", wraplength=560).pack(anchor="w", pady=2)

        diagnostic = ttk.LabelFrame(parent, text="ISBN Lookup Test", padding=10)
        diagnostic.grid(row=0, column=1, rowspan=2, sticky="nsew")
        ttk.Label(
            diagnostic,
            text="Test one provider's metadata retrieval capability to diagnose missing metadata or provider failures.",
            wraplength=390,
        ).pack(anchor="w", pady=(0, 6))
        self._provider_test_panel = MetadataProviderTestPanel(
            diagnostic, google_books_api_key=self._load_google_books_key()
        )
        self._provider_test_panel.pack(fill="both", expand=True)

    def _build_api_management(self, parent):
        parent.columnconfigure(1, weight=1)
        google = ttk.LabelFrame(parent, text="Google Books", padding=12)
        google.pack(fill="x", anchor="n")
        ttk.Label(
            google,
            text="The optional key identifies BookLedger for public Google Books lookups. Test Lookup runs a sample ISBN metadata request.",
            wraplength=920,
        ).grid(row=0, column=0, columnspan=7, sticky="w", pady=(0, 8))
        ttk.Label(google, text="Google Books API key").grid(row=1, column=0, sticky="w", padx=(0, 8))
        self.google_books_key_var = tk.StringVar(value=self._load_google_books_key())
        self.google_books_key_entry = ttk.Entry(google, textvariable=self.google_books_key_var, show="•", width=28)
        self.google_books_key_entry.grid(row=1, column=1, sticky="ew", padx=(0, 6))
        self.google_books_show_var = tk.BooleanVar(value=False)

        def toggle_key_visibility():
            visible = self.google_books_show_var.get()
            self.google_books_key_entry.configure(show="" if visible else "•")
            show_button.configure(text="Hide" if visible else "Show")

        show_button = ttk.Button(google, text="Show", command=lambda: (self.google_books_show_var.set(not self.google_books_show_var.get()), toggle_key_visibility()))
        show_button.grid(row=1, column=2, padx=3)
        ttk.Button(google, text="Test Lookup", command=self._test_google_books_lookup).grid(row=1, column=3, padx=3)
        ttk.Button(google, text="Save", command=self._save_google_books_key).grid(row=1, column=4, padx=3)
        ttk.Button(google, text="Remove", command=self._remove_google_books_key).grid(row=1, column=5, padx=3)
        ttk.Button(google, text="?", width=3, command=lambda: self._show_api_help("Google Books")).grid(row=1, column=6, padx=(3, 0))
        configuration_messages = list(self._configuration_warnings)
        if self.provider_settings_store.warning and self.provider_settings_store.warning not in configuration_messages:
            configuration_messages.insert(0, self.provider_settings_store.warning)
        config_warning = " ".join(configuration_messages)
        self.google_books_api_status = tk.StringVar(
            value=config_warning or "API key is optional; saved keys remain masked."
        )
        ttk.Label(google, textvariable=self.google_books_api_status, foreground="#64748b", wraplength=920).grid(row=2, column=0, columnspan=7, sticky="w", pady=(8, 0))

        planned = ttk.LabelFrame(parent, text="Planned API integrations", padding=12)
        planned.pack(fill="x", anchor="n", pady=(12, 0))
        for row, name in enumerate(("ISBNdb", "BigBook", "Hardcover")):
            ttk.Label(planned, text=name, width=18).grid(row=row, column=0, sticky="w", pady=3)
            ttk.Label(planned, text="Planned · API configuration unavailable until integrated.").grid(row=row, column=1, sticky="w", pady=3)
            ttk.Button(planned, text="?", width=3, command=lambda provider=name: self._show_api_help(provider)).grid(row=row, column=2, padx=(8, 0))

    def _show_api_help(self, provider):
        if provider == "Google Books":
            messagebox.showinfo(
                "Google Books API Help",
                "BookLedger uses the Google Books API to retrieve public book metadata. An API key identifies the application and is optional for the current integration. Google explains API keys and credentials here:\n\nhttps://developers.google.com/books/docs/v1/using",
                parent=self,
            )
        else:
            messagebox.showinfo(
                f"{provider} Help",
                f"{provider} is planned but is not integrated. BookLedger cannot configure credentials or connect to this provider yet.",
                parent=self,
            )

    def _build_storage_settings(self, parent):
        parent.columnconfigure((0, 1, 2), weight=1, uniform="storage")
        backups = ttk.LabelFrame(parent, text="Backup and verification", padding=12)
        backups.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        ttk.Button(backups, text="Back Up Now", command=self.create_backup).pack(fill="x", pady=3)
        ttk.Button(backups, text="Restore Backup…", command=self.restore_backup).pack(fill="x", pady=3)
        ttk.Button(backups, text="Export to CSV…", command=self.export_inventory_csv).pack(fill="x", pady=3)
        ttk.Button(backups, text="Verify Database", command=self.verify_database).pack(fill="x", pady=3)

        recovery = ttk.LabelFrame(parent, text="Copy and storage recovery", padding=12)
        recovery.grid(row=0, column=1, sticky="nsew", padx=6)
        count = self.lifecycle.trash_count()
        ttk.Button(recovery, text="Undo Delete", state="normal" if count else "disabled", command=self.restore_latest).pack(fill="x", pady=3)
        ttk.Button(recovery, text="Retry Recovery", command=self.retry_storage_recovery).pack(fill="x", pady=3)
        ttk.Button(recovery, text="Clear Trash…", state="normal" if count else "disabled", command=self.clear_trash).pack(fill="x", pady=3)
        ttk.Button(recovery, text="Purge Data…", command=self.purge_data).pack(fill="x", pady=3)

        logging_panel = ttk.LabelFrame(parent, text="Diagnostic log", padding=12)
        logging_panel.grid(row=0, column=2, sticky="nsew", padx=(6, 0))
        self.logging_var = tk.BooleanVar(value=self._logging_enabled)
        self.view_log_button = ttk.Button(logging_panel, text="View Log", command=self.view_log, state="normal" if self._logging_enabled else "disabled")
        self.view_log_button.pack(fill="x", pady=3)
        self.clear_log_button = ttk.Button(logging_panel, text="Clear Log…", command=self.clear_log, state="normal" if self._logging_enabled else "disabled")
        self.clear_log_button.pack(fill="x", pady=3)
        ttk.Checkbutton(logging_panel, text="Enable Logging", variable=self.logging_var, command=self._toggle_logging).pack(anchor="w", pady=(8, 3))
        self.logging_status_var = tk.StringVar(value=self._logging_warning or ("Logging is enabled." if self._logging_enabled else "Logging is off."))
        ttk.Label(logging_panel, textvariable=self.logging_status_var, foreground="#64748b", wraplength=220).pack(anchor="w", pady=(4, 0))

    def _build_poster_setup(self, parent):
        ttk.Label(parent, text="Poster setup is reserved for future development.", foreground="#64748b").pack(anchor="nw")

    def _build_preferences(self, parent):
        parent.columnconfigure((0, 1), weight=1, uniform="preferences")
        parent.rowconfigure((0, 1), weight=1, uniform="preferences_rows")
        self._build_value_list_editor(
            parent, "Genre", "genre", self.catalog.list_genres,
            lambda value: self.catalog.value_assignment_count("genre", value),
            self.catalog.add_genre, self.catalog.rename_genre, self.catalog.delete_genre,
            row=0, column=0,
        )
        self._build_value_list_editor(
            parent, "Format", "format", self.catalog.list_formats,
            lambda value: self.catalog.value_assignment_count("format", value),
            self.catalog.add_format, self.catalog.rename_format, self.catalog.delete_format,
            row=0, column=1,
        )
        self._build_value_list_editor(
            parent, "Location", "location", self.catalog.list_locations,
            self.catalog.location_assignment_count,
            self.catalog.add_location, self.catalog.rename_location, self.catalog.delete_location,
            row=1, column=0,
        )
        themes = ttk.LabelFrame(parent, text="Themes", padding=12)
        themes.grid(row=1, column=1, sticky="nsew", padx=(6, 0), pady=(6, 0))
        ttk.Label(themes, text="Theme selection is not available yet.", foreground="#64748b").grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))
        ttk.Label(themes, text="Themes:").grid(row=1, column=0, sticky="w", padx=(0, 6))
        ttk.Combobox(themes, values=("Unavailable",), state="disabled", width=22).grid(row=1, column=1, sticky="ew")
        ttk.Button(themes, text="Preview", state="disabled").grid(row=2, column=0, pady=(10, 0), sticky="w")
        ttk.Button(themes, text="Apply", state="disabled").grid(row=2, column=1, pady=(10, 0), sticky="w")

    def _build_value_list_editor(self, parent, title, kind, list_values, assignment_count, add_value, rename_value, delete_value, *, row, column):
        panel = ttk.LabelFrame(parent, text=title, padding=10)
        panel.grid(row=row, column=column, sticky="nsew", padx=(0, 6) if column == 0 else (6, 0), pady=(0, 6) if row == 0 else (6, 0))
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(0, weight=1)
        list_frame = ttk.Frame(panel)
        list_frame.grid(row=0, column=0, sticky="nsew")
        list_frame.rowconfigure(0, weight=1)
        canvas = tk.Canvas(list_frame, height=166, highlightthickness=0, borderwidth=0)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        rows = ttk.Frame(canvas)
        rows.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        window_id = canvas.create_window((0, 0), window=rows, anchor="nw")
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window_id, width=event.width))
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        list_frame.columnconfigure(0, weight=1)

        status_var = tk.StringVar(value="")
        ttk.Label(panel, textvariable=status_var, foreground="#64748b", wraplength=420).grid(row=1, column=0, sticky="w", pady=(5, 4))
        add_row = ttk.Frame(panel)
        add_row.grid(row=2, column=0, sticky="ew")
        add_entry = ttk.Entry(add_row)
        add_entry.pack(side="left", fill="x", expand=True)

        def refresh():
            for child in rows.winfo_children():
                child.destroy()
            for index, value in enumerate(list_values()):
                item = ttk.Frame(rows)
                item.grid(row=index, column=0, sticky="ew", pady=1)
                item.columnconfigure(0, weight=1)
                name_label = ttk.Label(item, text=value, anchor="w")
                name_label.grid(row=0, column=0, sticky="ew", padx=(0, 4))
                count = assignment_count(value)
                rename_button = ttk.Button(item, text="Rename", width=8)
                delete_button = ttk.Button(
                    item, text="Delete", width=7,
                    state="disabled" if count else "normal",
                    command=lambda name=value: delete(name),
                )
                rename_button.grid(row=0, column=1, padx=2)
                delete_button.grid(row=0, column=2, padx=2)
                if count:
                    explanation = f"Cannot delete this {kind} because one or more books are assigned to it. Rename it to migrate the assignments, or update those books first."
                    info = ttk.Label(item, text="ⓘ", foreground="#64748b", cursor="question_arrow")
                    info.grid(row=0, column=3, padx=(4, 0))
                    info.bind("<Enter>", lambda event, message=explanation: self._show_hover_tooltip(event, message))
                    info.bind("<Leave>", self._hide_hover_tooltip)
                    delete_button.bind("<Enter>", lambda event, message=explanation: self._show_hover_tooltip(event, message))
                    delete_button.bind("<Leave>", self._hide_hover_tooltip)

                def begin_rename(old_value=value, row_widget=item, label_widget=name_label, button=rename_button):
                    label_widget.grid_remove()
                    button.grid_remove()
                    edit = ttk.Entry(row_widget)
                    edit.insert(0, old_value)
                    edit.grid(row=0, column=0, sticky="ew", padx=(0, 4))

                    def save_rename():
                        try:
                            replacement = rename_value(old_value, edit.get())
                        except (ValueError, OSError, sqlite3.Error) as exc:
                            status_var.set(str(exc))
                            return
                        status_var.set(f"{title} saved.")
                        refresh()

                    ttk.Button(row_widget, text="Save", width=7, command=save_rename).grid(row=0, column=1, padx=2)
                    ttk.Button(row_widget, text="Cancel", width=7, command=refresh).grid(row=0, column=2, padx=2)
                    edit.focus_set()
                    edit.selection_range(0, "end")

                rename_button.configure(command=begin_rename)
            canvas.yview_moveto(0)

        def add():
            try:
                value = add_value(add_entry.get())
            except (ValueError, OSError, sqlite3.Error) as exc:
                status_var.set(str(exc))
                return
            add_entry.delete(0, "end")
            status_var.set(f"{title} added.")
            refresh()
            canvas.yview_moveto(1.0)

        def delete(value):
            try:
                delete_value(value)
            except (ValueError, OSError, sqlite3.Error) as exc:
                status_var.set(str(exc))
                refresh()
                return
            status_var.set(f"{title} deleted.")
            refresh()

        ttk.Button(add_row, text="Add New", command=add).pack(side="left", padx=(6, 0))
        refresh()

    def _show_hover_tooltip(self, event, message):
        self._hide_hover_tooltip()
        try:
            tip = tk.Toplevel(self)
            tip.wm_overrideredirect(True)
            tip.wm_geometry(f"+{event.x_root + 12}+{event.y_root + 12}")
            ttk.Label(tip, text=message, wraplength=340, padding=8, relief="solid").pack()
            self._hover_tooltip = tip
        except tk.TclError:
            self._hover_tooltip = None

    def _hide_hover_tooltip(self, _event=None):
        tip = getattr(self, "_hover_tooltip", None)
        if tip is not None:
            try:
                tip.destroy()
            except tk.TclError:
                pass
            self._hover_tooltip = None

    def _provider_drag_start(self, event, provider_id):
        self._provider_drag_id = provider_id

    def _provider_drag_motion(self, event):
        if not getattr(self, "_provider_drag_id", None):
            return
        rows = list(self._provider_order)
        moving = self._provider_drag_id
        target_y = event.y_root
        for provider_id in rows:
            if provider_id == moving:
                continue
            row = self._provider_rows[provider_id]
            midpoint = row.winfo_rooty() + row.winfo_height() / 2
            if target_y < midpoint:
                rows.remove(moving)
                rows.insert(rows.index(provider_id), moving)
                break
        else:
            rows.remove(moving)
            rows.append(moving)
        self._reorder_provider_rows(rows)

    def _provider_drag_end(self, _event):
        self._provider_drag_id = None

    def _reorder_provider_rows(self, provider_ids):
        self._provider_order = list(provider_ids)
        for row in self._provider_rows.values():
            row.pack_forget()
        for provider_id in self._provider_order:
            if provider_id in self._provider_rows:
                self._provider_rows[provider_id].pack(fill="x")

    def _save_provider_settings(self):
        order = list(self._provider_order)
        self.provider_settings.order = order
        self.provider_settings.enabled = {
            provider_id: bool(variable.get()) for provider_id, variable in self._provider_variables.items()
        }
        try:
            saved_path = self.provider_settings_store.save(self.provider_settings)
        except OSError as exc:
            self._provider_config_status.set(f"Could not save provider settings: {exc}")
            return
        self.metadata_lookup = MetadataLookupService(
            build_providers(self.provider_settings, self._load_google_books_key())
        )
        self._provider_config_status.set(f"Provider settings saved to {saved_path}")

    def _restore_provider_defaults(self):
        self.provider_settings = ProviderSettings.defaults()
        for provider_id, variable in self._provider_variables.items():
            variable.set(True)
        self._reorder_provider_rows(list(self.provider_settings.order))
        self._save_provider_settings()

    def _load_google_books_key(self):
        try:
            value = self.config_store.get(("api_keys", "google_books"), "")
            return value if isinstance(value, str) else ""
        except (OSError, ValueError, AttributeError):
            return ""

    def _apply_google_books_key(self, api_key):
        self.metadata_lookup = MetadataLookupService(
            build_providers(self.provider_settings, api_key)
        )
        panel = getattr(self, "_provider_test_panel", None)
        if panel is not None:
            panel._google_books_api_key = api_key

    def _save_google_books_key(self):
        try:
            api_key = self.google_books_key_var.get().strip()
            self.config_store.set(("api_keys", "google_books"), api_key)
            self._apply_google_books_key(api_key)
        except (OSError, ValueError) as exc:
            self.google_books_api_status.set(f"Could not save Google Books settings: {exc}")
            return False
        self.google_books_api_status.set("Google Books API settings saved.")
        return True

    def _remove_google_books_key(self):
        if not messagebox.askyesno(
            "Remove Google Books API key?",
            "Remove the saved Google Books API key from BookLedger? Other Google Books settings will be kept.",
            parent=self,
        ):
            return
        try:
            existed = self.config_store.get(("api_keys", "google_books"), None) is not None
            if existed:
                self.config_store.remove(("api_keys", "google_books"))
            self.google_books_key_var.set("")
            self._apply_google_books_key("")
        except (OSError, ValueError) as exc:
            self.google_books_api_status.set(f"Could not remove Google Books API key: {exc}")
            return
        self.google_books_api_status.set(
            "Saved Google Books API key removed." if existed else "No saved Google Books API key was present."
        )

    def _test_google_books_lookup(self):
        api_key = self.google_books_key_var.get().strip()
        self.google_books_api_status.set("Testing a sample Google Books metadata lookup…")

        def worker():
            try:
                result = GoogleBooksProvider(api_key).lookup("9780306406157")
                succeeded = result.status != "Lookup failed"
                error = result.failure_kind or "provider error"
            except Exception as exc:
                succeeded = False
                error = type(exc).__name__

            def complete():
                try:
                    if self.winfo_exists():
                        self.google_books_api_status.set(
                            "Sample metadata lookup succeeded." if succeeded
                            else f"Sample metadata lookup failed: {error or 'provider error'}"
                        )
                except tk.TclError:
                    pass

            try:
                self.after(0, complete)
            except tk.TclError:
                pass

        try:
            threading.Thread(target=worker, name="BookLedgerGoogleBooksTest", daemon=True).start()
        except Exception as exc:
            self.google_books_api_status.set(f"Could not start Google Books lookup: {type(exc).__name__}")

    def open_isbn_lookup_test(self):
        return MetadataProviderTestDialog(
            self, google_books_api_key=self._load_google_books_key()
        )

    def open_add_form(self):
        BookForm(self, service=self.catalog, photo_service=self.photos, metadata_lookup=self.metadata_lookup, on_saved=lambda: self._after_save("Book saved."))

    def open_selected_edit(self, copy_id=None):
        if copy_id is None:
            tree = getattr(self, "tree", None)
            try:
                if tree is None or not tree.winfo_exists():
                    self.status_var.set("Select a physical copy first.")
                    return
                selection = tree.selection()
            except tk.TclError:
                self.status_var.set("Select a physical copy first.")
                return
            if not selection:
                self.status_var.set("Select a physical copy first.")
                return
            copy_id = int(selection[0])
        else:
            copy_id = int(copy_id)
        row = self.catalog.get_copy(copy_id)
        if not row:
            self.status_var.set("That copy could not be found. Refresh and try again.")
            return
        BookForm(self, service=self.catalog, photo_service=self.photos, metadata_lookup=getattr(self, "metadata_lookup", None), on_saved=lambda: self._after_save("Book updated."), existing=row)

    def _sale_history_text(self, history):
        if not history:
            return "No sale transactions recorded.\n"
        lines = []
        for number, sale in enumerate(history, start=1):
            is_voided = bool(sale.get("voided_at"))
            status = "Voided" if is_voided else "Completed"
            lines.extend((
                f"Sale {number} — {status}",
                f"Transaction ID: {sale['sale_id']}",
                f"Date Sold: {sale['sale_date']}",
                f"Original Price: {self.money(sale['price_minor'])}",
                f"Transaction Status: {status}",
            ))
            if is_voided:
                lines.append(f"Sale Voided: {sale['voided_at']}")
                lines.append(f"Reason: {sale.get('void_reason') or 'Not recorded (legacy reversal)'}")
            lines.append("")
        return "\n".join(lines)

    def open_copy_details(self, copy_id):
        row = self.catalog.get_copy_details(int(copy_id))
        if not row:
            self.status_var.set("That copy could not be found. Refresh and try again.")
            return
        dialog = tk.Toplevel(self)
        dialog.title(f"View Details · {row['copy_code']}")
        dialog.transient(self)
        dialog.geometry("620x650")
        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="View Details", font=("Segoe UI", 16, "bold")).pack(anchor="w", pady=(0, 12))
        fields = (
            ("Title", row.get("title")), ("Author", row.get("author")), ("ISBN", row.get("isbn")),
            ("Genre", row.get("genre")), ("Publisher", row.get("publisher")),
            ("Publication Year", row.get("publication_year")), ("Edition", row.get("edition")),
            ("Page Count", row.get("page_count")), ("Book Details", row.get("book_details")),
            ("SRP (reference)", self.money(row["srp_minor"]) if row.get("srp_minor") is not None else None),
            ("Physical Copy", self._physical_copy_label(row)),
            ("Internal Copy ID", row.get("copy_id")), ("Copy Code", row.get("copy_code")), ("Format", row.get("format")),
            ("Condition", row.get("condition")), ("Location", row.get("location")),
            ("Status", row.get("status")),
            ("Price", self.money(row["display_price_minor"])),
            ("Metadata", row.get("metadata_source")),
        )
        text_frame = ttk.Frame(frame)
        text_frame.pack(fill="both", expand=True)
        text = tk.Text(text_frame, wrap="word", height=24, relief="flat", background=dialog.cget("background"))
        scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)
        text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        for label, value in fields:
            if value not in (None, ""):
                text.insert("end", f"{label}: {value}\n\n")
        text.insert("end", "Sale History / Void Log\n\n")
        text.insert("end", self._sale_history_text(row.get("sale_history", ())))
        text.configure(state="disabled")
        ttk.Button(frame, text="Close", command=dialog.destroy).pack(anchor="e", pady=(12, 0))

    def _after_save(self, message):
        self.status_var.set(message)
        self.refresh_current()

    def export_inventory_csv(self):
        destination = filedialog.asksaveasfilename(
            parent=self,
            title="Export BookLedger inventory",
            initialdir=self.paths.root,
            initialfile="bookledger-inventory.csv",
            defaultextension=".csv",
            filetypes=[("CSV file", "*.csv"), ("All files", "*.*")],
        )
        if not destination:
            return
        columns = (
            ("copy_id", "Copy ID"),
            ("copy_code", "Copy Code"),
            ("copy_number", "Copy Number"),
            ("title", "Title"),
            ("author", "Author"),
            ("isbn", "ISBN"),
            ("genre", "Genre"),
            ("publisher", "Publisher"),
            ("publication_year", "Publication Year"),
            ("edition", "Edition"),
            ("page_count", "Page Count"),
            ("book_details", "Book Details"),
            ("srp_minor", "SRP (PHP)"),
            ("format", "Format"),
            ("condition", "Condition"),
            ("location", "Location"),
            ("price_minor", "Price (PHP)"),
            ("status", "Status"),
            ("metadata_source", "Metadata Source"),
            ("metadata_status", "Metadata Status"),
        )
        try:
            copies = self.catalog.list_copies()
            with open(destination, "w", encoding="utf-8", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow([label for _key, label in columns])
                for copy in copies:
                    values = []
                    for key, _label in columns:
                        value = copy.get(key)
                        if key in ("price_minor", "srp_minor"):
                            value = "" if value is None else format(Decimal(int(value)) / Decimal(100), ".2f")
                        values.append(value if value is not None else "")
                    writer.writerow(values)
        except (OSError, csv.Error, ValueError) as exc:
            messagebox.showerror("CSV export failed", f"The inventory could not be exported: {exc}", parent=self)
            return
        self.status_var.set(f"Exported {len(copies)} inventory copies to {Path(destination).name}.")
        messagebox.showinfo(
            "CSV export complete",
            f"Exported {len(copies)} physical copies to:\n{destination}",
            parent=self,
        )

    def _read_logging_enabled(self):
        try:
            value = self.config_store.get(("logging", "enabled"), False)
            return value if isinstance(value, bool) else False
        except (OSError, ValueError):
            return False

    def _configure_optional_logging(self, enabled):
        logger = self._optional_logger
        for handler in tuple(logger.handlers):
            logger.removeHandler(handler)
            try:
                handler.flush()
                handler.close()
            except OSError:
                pass
        logger.setLevel(logging.INFO)
        logger.propagate = False
        if not enabled:
            return ""
        try:
            handler = logging.FileHandler(self.paths.root / "log.txt", mode="a", encoding="utf-8", delay=False)
            handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
            logger.addHandler(handler)
            return ""
        except OSError as exc:
            return f"Could not open log.txt for writing: {exc}"

    def _toggle_logging(self):
        requested = bool(self.logging_var.get())
        previous = self._logging_enabled
        warning = self._configure_optional_logging(requested)
        if warning:
            self._configure_optional_logging(previous)
            self.logging_var.set(previous)
            self.logging_status_var.set(warning)
            return
        try:
            self.config_store.set(("logging", "enabled"), requested)
        except (OSError, ValueError) as exc:
            self._configure_optional_logging(previous)
            self.logging_var.set(previous)
            self.logging_status_var.set(f"Could not save logging preference: {exc}")
            return
        self._logging_enabled = requested
        state = "normal" if requested else "disabled"
        self.view_log_button.configure(state=state)
        self.clear_log_button.configure(state=state)
        self.logging_status_var.set("Logging is enabled." if requested else "Logging is off.")
        if requested:
            self._optional_logger.info("diagnostic_logging_enabled")

    def view_log(self):
        if not self._logging_enabled:
            return
        path = self.paths.root / "log.txt"
        if not path.is_file():
            messagebox.showinfo("Diagnostic log", "No log file has been created yet.", parent=self)
            return
        try:
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except OSError as exc:
            messagebox.showerror("Could not open log", f"The diagnostic log could not be opened: {exc}", parent=self)

    def clear_log(self):
        if not self._logging_enabled:
            return
        if not messagebox.askyesno(
            "Clear diagnostic log?", "Clear the contents of log.txt? The log file will remain in place.", parent=self
        ):
            return
        path = self.paths.root / "log.txt"
        try:
            active_handlers = [
                handler for handler in self._optional_logger.handlers
                if isinstance(handler, logging.FileHandler) and handler.stream is not None
            ]
            if active_handlers:
                for handler in active_handlers:
                    handler.acquire()
                    try:
                        handler.flush()
                        handler.stream.seek(0)
                        handler.stream.truncate()
                        handler.flush()
                    finally:
                        handler.release()
            else:
                path.write_text("", encoding="utf-8")
            self.logging_status_var.set("Diagnostic log cleared.")
        except OSError as exc:
            messagebox.showerror("Could not clear log", f"The diagnostic log could not be cleared: {exc}", parent=self)

    def create_backup(self):
        try:
            path = self.backups.create_backup()
            self.status_var.set(f"Backup created: {path.name}")
            messagebox.showinfo("Backup complete", f"Backup saved to:\n{path}", parent=self)
        except Exception as exc:
            messagebox.showerror("Backup failed", str(exc), parent=self)

    def restore_backup(self):
        path = filedialog.askopenfilename(parent=self, title="Choose a BookLedger backup", initialdir=self.paths.backups, filetypes=[("BookLedger backup", "*.zip"), ("All files", "*.*")])
        if not path:
            return
        ok, message = self.backups.verify_archive(path)
        if not ok:
            messagebox.showerror("Backup verification failed", message, parent=self)
            return
        if not messagebox.askyesno("Restore backup?", "Restoring replaces the current database and photo collection. A safety backup of the current data will be created first. Continue?", parent=self):
            return
        try:
            self.backups.restore_backup(path)
            self.status_var.set(f"Restored backup: {Path(path).name}")
            self.refresh_current()
            messagebox.showinfo("Restore complete", "The backup was restored and the database passed its integrity check.", parent=self)
        except Exception as exc:
            messagebox.showerror("Restore failed", f"The backup could not be restored: {exc}", parent=self)

    def verify_database(self):
        report = self.verifier.verify()
        if report.ok:
            messagebox.showinfo("Database check", report.message, parent=self)
        else:
            messagebox.showwarning("Database check", report.message, parent=self)

    def restore_latest(self):
        try:
            copy_id = self.lifecycle.restore_latest()
            if copy_id is not None:
                self.status_var.set(f"Restored Copy ID {copy_id}.")
                self.refresh_current()
        except Exception as exc:
            messagebox.showerror("Restore Failed", str(exc), parent=self)

    def retry_storage_recovery(self):
        failures = self.lifecycle.retry_pending_operations()
        if failures:
            messagebox.showerror("Recovery Needs Attention", "Some storage operations remain unresolved:\n" + "\n".join(failures), parent=self)
        else:
            messagebox.showinfo("Recovery Complete", "All pending storage operations were completed.", parent=self)
        self.refresh_current()

    def clear_trash(self):
        if not messagebox.askyesno("Permanently Clear Trash?", "This permanently removes trashed copies, their sales history, and unshared photos. This cannot be undone.", parent=self):
            return
        try:
            count = self.lifecycle.clear_trash()
            self.status_var.set(f"Permanently removed {count} trashed copy/copies.")
            self.refresh_current()
        except Exception as exc:
            messagebox.showerror("Clear Trash Incomplete", str(exc), parent=self)

    def purge_data(self):
        if not messagebox.askyesno("Reset BookLedger Data?", "This removes the database, photos, Trash, locations, and other data under the portable data folder. Application configuration, including metadata provider settings and the Google Books API key, remains in config.json. Backups in the root backups folder are retained. Create a backup first if you may need this data.", parent=self):
            return
        from tkinter import simpledialog
        typed = simpledialog.askstring("Confirm Purge", "Type PURGE to permanently reset BookLedger data:", parent=self)
        if typed != "PURGE":
            return
        try:
            self.lifecycle.purge()
            self.paths.prepare()
            self.db = Database(self.paths.database)
            self.catalog = CatalogService(self.db, self.paths.data, config_store=self.config_store)
            self.photos = PhotoService(self.paths.photos, self.paths.trash)
            self.lifecycle = CopyLifecycleService(self.db, self.paths.data)
            self.verifier = VerificationService(self.db, self.paths.data)
            self.backups = BackupService(self.db, self.paths.data, self.paths.backups)
            self.metadata_lookup = MetadataLookupService(
                build_providers(self.provider_settings, self._load_google_books_key())
            )
            self.status_var.set("BookLedger data was purged. Root-level backups were retained.")
            self.show_page("Dashboard")
        except Exception as exc:
            messagebox.showerror("Purge Incomplete", f"BookLedger could not complete the purge. The data folder may be partially reset: {exc}", parent=self)

    def _open_path(self, path: Path):
        try:
            if sys.platform == "win32":
                import os
                os.startfile(path)
            else:
                messagebox.showinfo("Data folder", str(path), parent=self)
        except Exception as exc:
            messagebox.showerror("Could not open folder", str(exc), parent=self)

    @staticmethod
    def money(minor):
        return f"₱{(minor or 0) / 100:,.2f}"


def main():
    app = BookLedgerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
