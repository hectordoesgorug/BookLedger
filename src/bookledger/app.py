from __future__ import annotations
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime
from pathlib import Path
import shutil
import sys

from bookledger import __version__
from bookledger.config import APP_NAME, APPROVED_GENRES, COPY_STATUSES
from bookledger.db.database import Database
from bookledger.paths import AppPaths
from bookledger.services.backups import BackupService
from bookledger.services.catalog import CatalogService
from bookledger.services.photos import PhotoService
from bookledger.ui.forms import BookForm

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
        self.db = Database(self.paths.database)
        self.catalog = CatalogService(self.db, self.paths.data)
        self.photos = PhotoService(self.paths.photos)
        self.backups = BackupService(self.db, self.paths.data, self.paths.backups)
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
        for name, icon in (("Dashboard", "⌂"), ("Catalog", "▤"), ("Inventory", "▦"), ("Acquisitions", "+"), ("Sales", "↗"), ("Reports", "▥"), ("Settings", "⚙")):
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
        for child in self.workspace.winfo_children():
            child.destroy()

    def show_page(self, name):
        self.current_page = name
        self.page_title.configure(text=name)
        self._clear_workspace()
        if name in ("Catalog", "Inventory"):
            self._build_catalog_page(inventory=(name == "Inventory"))
        elif name == "Dashboard":
            self._build_dashboard()
        elif name == "Acquisitions":
            self._build_acquisitions()
        elif name == "Sales":
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
        metrics = [("Total copies", counts.get("Total copies", 0)), ("Available", counts.get("Available", 0)), ("Listed", counts.get("Listed", 0)), ("Not for Sale", counts.get("Not for Sale", 0)), ("Sold", counts.get("Sold", 0)), ("Book records", counts.get("Bibliographic records", 0))]
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
            self.tree.insert("", "end", iid=str(row["copy_id"]), values=(row["copy_code"], row["title"], row["author"], row["status"], self.money(row["price_minor"])))
        self.tree.bind("<Double-1>", lambda _e: self.open_selected_edit())

    def _build_catalog_page(self, inventory=False):
        top = ttk.Frame(self.workspace)
        top.pack(fill="x", pady=(0, 12))
        ttk.Label(top, text="Search and filter physical copies" if inventory else "Search titles, authors, ISBNs, and individual copies", foreground="#64748b").pack(side="left")
        ttk.Button(top, text="＋ Add Book", style="Primary.TButton", command=self.open_add_form).pack(side="right")
        filters = ttk.Frame(self.workspace)
        filters.pack(fill="x", pady=(0, 12))
        self.status_filter = tk.StringVar(value="All")
        self.genre_filter = tk.StringVar(value="All")
        ttk.Label(filters, text="Status").pack(side="left", padx=(0, 6))
        status_combo = ttk.Combobox(filters, textvariable=self.status_filter, values=("All",) + COPY_STATUSES, state="readonly", width=16)
        status_combo.pack(side="left", padx=(0, 16))
        ttk.Label(filters, text="Genre").pack(side="left", padx=(0, 6))
        genre_combo = ttk.Combobox(filters, textvariable=self.genre_filter, values=("All",) + APPROVED_GENRES, state="readonly", width=22)
        genre_combo.pack(side="left", padx=(0, 16))
        ttk.Button(filters, text="Apply filters", command=self._populate_catalog).pack(side="left")
        ttk.Button(filters, text="Clear", command=self._clear_filters).pack(side="left", padx=6)
        ttk.Button(filters, text="Edit selected", command=self.open_selected_edit).pack(side="right")
        ttk.Label(filters, text="Double-click a row to edit", foreground="#64748b").pack(side="right", padx=12)
        frame = ttk.Frame(self.workspace)
        frame.pack(fill="both", expand=True)
        self._make_tree(frame, columns=("code", "title", "author", "genre", "status", "price", "location"), headings=("Copy ID", "Title", "Author", "Genre", "Status", "Price (PHP)", "Location"), height=18)
        self.tree.bind("<Double-1>", lambda _e: self.open_selected_edit())
        self._populate_catalog()

    def _make_tree(self, parent, *, columns, headings, height=15):
        container = ttk.Frame(parent)
        container.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(container, columns=columns, show="headings", height=height, selectmode="browse")
        widths = {"code": 110, "title": 240, "author": 180, "genre": 130, "status": 115, "price": 110, "location": 130}
        for col, heading in zip(columns, headings):
            self.tree.heading(col, text=heading)
            self.tree.column(col, width=widths.get(col, 130), minwidth=75, stretch=True)
        ybar = ttk.Scrollbar(container, orient="vertical", command=self.tree.yview)
        xbar = ttk.Scrollbar(container, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        ybar.grid(row=0, column=1, sticky="ns")
        xbar.grid(row=1, column=0, sticky="ew")
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

    def _populate_catalog(self):
        if not hasattr(self, "tree") or not self.tree.winfo_exists():
            return
        self.tree.delete(*self.tree.get_children())
        search = self.global_search.get()
        status = getattr(self, "status_filter", tk.StringVar(value="All")).get()
        genre = getattr(self, "genre_filter", tk.StringVar(value="All")).get()
        rows = self.catalog.list_copies(search, status, genre)
        columns = self.tree["columns"]
        for row in rows:
            values = {
                "code": row["copy_code"], "title": row["title"], "author": row["author"], "genre": row["genre"],
                "status": row["status"], "price": self.money(row["price_minor"]), "location": row["location"]
            }
            self.tree.insert("", "end", iid=str(row["copy_id"]), values=tuple(values[c] for c in columns))
        self.status_var.set(f"{len(rows)} physical copy/copies shown")

    def _clear_filters(self):
        self.global_search.set("")
        self.status_filter.set("All")
        self.genre_filter.set("All")
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
        ttk.Label(top, text="Completed sales and historical sale details", foreground="#64748b").pack(side="left")
        frame = ttk.Frame(self.workspace)
        frame.pack(fill="both", expand=True)
        self._make_tree(frame, columns=("code", "title", "author", "sale_date", "sale_price", "status"), headings=("Copy ID", "Title", "Author", "Sale date", "Actual sale price", "Current status"), height=18)
        rows = [r for r in self.catalog.list_copies() if r.get("actual_sale_price_minor") is not None]
        for row in rows:
            self.tree.insert("", "end", iid=str(row["copy_id"]), values=(row["copy_code"], row["title"], row["author"], row["sale_date"], self.money(row["actual_sale_price_minor"]), row["status"]))
        self.tree.bind("<Double-1>", lambda _e: self.open_selected_edit())
        if not rows:
            self.status_var.set("No sales recorded yet")

    def _build_reports(self):
        counts = self.catalog.counts()
        frame = ttk.LabelFrame(self.workspace, text="Inventory summary", padding=18)
        frame.pack(fill="x", anchor="n")
        for label in ("Total copies", "Bibliographic records", *COPY_STATUSES):
            ttk.Label(frame, text=label, width=25).pack(side="left", padx=(0, 4))
            ttk.Label(frame, text=str(counts.get(label, 0)), font=("Segoe UI", 10, "bold"), width=8).pack(side="left", padx=(0, 18))
        ttk.Label(self.workspace, text="Further reports will be added after the core catalog and sales workflows are stable.", foreground="#64748b").pack(anchor="w", pady=18)

    def _build_settings(self):
        panel = ttk.LabelFrame(self.workspace, text="Portable data and backups", padding=18)
        panel.pack(fill="x", anchor="n")
        ttk.Label(panel, text=f"Data folder: {self.paths.data}", wraplength=850).pack(anchor="w", pady=(0, 8))
        ttk.Label(panel, text=f"Database: {self.paths.database}", wraplength=850).pack(anchor="w", pady=(0, 12))
        row = ttk.Frame(panel)
        row.pack(anchor="w")
        ttk.Button(row, text="Back Up Now", style="Primary.TButton", command=self.create_backup).pack(side="left", padx=(0, 8))
        ttk.Button(row, text="Open Data Folder", command=lambda: self._open_path(self.paths.data)).pack(side="left", padx=8)
        ttk.Button(row, text="Verify Database", command=self.verify_database).pack(side="left", padx=8)
        ttk.Button(row, text="Restore Backup…", command=self.restore_backup).pack(side="left", padx=8)
        genres = ttk.LabelFrame(self.workspace, text="Approved genres", padding=16)
        genres.pack(fill="x", pady=16)
        ttk.Label(genres, text=" · ".join(APPROVED_GENRES), wraplength=900).pack(anchor="w")
        ttk.Label(genres, text="Genre options are controlled by the v1 approved list. Unknown provider categories must be recategorized before saving.", foreground="#64748b", wraplength=900).pack(anchor="w", pady=(8, 0))
        companion = ttk.LabelFrame(self.workspace, text="Android companion (planned)", padding=16)
        companion.pack(fill="x")
        ttk.Label(companion, text="The desktop data model is being designed for future local Wi-Fi pairing and photo/ISBN transfer. Pairing will be implemented after desktop stabilization.", wraplength=900).pack(anchor="w")

    def open_add_form(self):
        BookForm(self, service=self.catalog, photo_service=self.photos, on_saved=lambda: self._after_save("Book saved."))

    def open_selected_edit(self):
        tree = getattr(self, "tree", None)
        selection = tree.selection() if tree else ()
        if not selection:
            self.status_var.set("Select a physical copy first.")
            return
        copy_id = int(selection[0])
        row = self.catalog.get_copy(copy_id)
        if not row:
            self.status_var.set("That copy could not be found. Refresh and try again.")
            return
        BookForm(self, service=self.catalog, photo_service=self.photos, on_saved=lambda: self._after_save("Book updated."), existing=row)

    def _after_save(self, message):
        self.status_var.set(message)
        self.refresh_current()

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
        ok, message = self.db.integrity_check()
        if ok:
            messagebox.showinfo("Database check", "Database integrity check passed.", parent=self)
        else:
            messagebox.showerror("Database check", f"Integrity check failed: {message}", parent=self)

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
