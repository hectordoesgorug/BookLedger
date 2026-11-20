from __future__ import annotations
import csv
import logging
from logging.handlers import RotatingFileHandler
import os
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, font as tkfont
from pathlib import Path
import shutil
import sqlite3
import sys
import threading
import webbrowser
from decimal import Decimal
from calendar import monthrange
from datetime import date
from PIL import Image, ImageTk

from bookledger import __version__
from bookledger.config import APP_NAME, BOOK_CONDITIONS, COPY_STATUSES
from bookledger.db.database import Database
from bookledger.paths import AppPaths
from bookledger.config_store import AppConfigStore
from bookledger.services.backups import BackupService
from bookledger.services.catalog import CatalogService, SALE_VOID_REASONS
from bookledger.services.reports import ReportService
from bookledger.services.metadata import GoogleBooksProvider, MetadataLookupService
from bookledger.provider_registry import PROVIDER_REGISTRY, build_providers
from bookledger.provider_settings import ProviderSettings, ProviderSettingsStore
from bookledger.resources import (
    apply_application_icon,
    normalize_shop_url,
    render_svg_icon,
    resource_path,
    resolve_managed_logo,
    store_shop_logo,
    remove_obsolete_shop_logo,
)
from bookledger.services.photos import PhotoService
from bookledger.services.lifecycle import CopyLifecycleService
from bookledger.services.activity_log import log_activity
from bookledger.services.verification import VerificationService
from bookledger.ui.forms import BookForm
from bookledger.ui.scrolling import MouseWheelRouter
from bookledger.services.posters import PosterService
from bookledger.services.currency import CurrencyService, ExchangeRateService, SUPPORTED_CURRENCIES, format_money
from bookledger.ui.poster_designer import PosterDesigner, create_poster_for_copy
from bookledger.ui.provider_diagnostic import MetadataProviderTestDialog, MetadataProviderTestPanel
from bookledger.ui.mobile_app_setup import MobileAppSetupPanel
from bookledger.ui.catalog_text import catalog_display_title, combined_title, truncate_to_two_lines
from bookledger.services.mobile_connection import MobileConnectionService
from bookledger.services.mobile_incoming import MobileIncomingStore
from bookledger.services.mobile_activity import MobileActivityStore
from bookledger.services.single_instance import (
    LibraryAlreadyRunning,
    LibraryInstanceLock,
    LibraryLockError,
)
from bookledger.ui.status_colors import ERROR_COLOR, INVENTORY_STATUS_COLORS, NEUTRAL_COLOR, SUCCESS_COLOR, WARNING_COLOR, status_message_color

CATALOG_CARD_WIDTH = 250
CATALOG_CARD_GAP = 14
NAVIGATION_ITEMS = (
    ("Dashboard", "icon-dashboard.svg", "⌂"),
    ("Catalog", "icon-catalog.svg", "▤"),
    ("Inventory", "icon-inventory.svg", "▦"),
    ("Acquisitions", "icon-acquisitions.svg", "+"),
    ("Sale History", "icon-sale history.svg", "↗"),
    ("Reports", "icon-reports.svg", "▥"),
    ("Settings", "icon-settings.svg", "⚙"),
    ("About", "icon-help.svg", "?"),
)


def _currency_option(code):
    return f"{code} ({SUPPORTED_CURRENCIES[code]})"


def _currency_code(option):
    return option.split(" ", 1)[0]
NAVIGATION_TOOLTIPS = {
    "Dashboard": "View inventory totals and recently added copies.",
    "Catalog": "Browse copy cards, search, filter and sort your library.",
    "Inventory": "View and sort physical copy details in a table.",
    "Acquisitions": "Add a book and its physical copy to the library.",
    "Sale History": "Review recorded sales and reversals.",
    "Reports": "Review inventory and sales summaries.",
    "Settings": "Configure mobile pairing, metadata, storage and preferences.",
    "About": "Read the BookLedger user guide.",
}
NAV_ICON_FRAME_SIZE = 36
NAV_ICON_CONTENT_SIZES = (26, 30, 32)
ABOUT_GUIDE_PAGES = (
    ("Dashboard", "About BookLedger", (
        ("p", None, "BookLedger is an offline-first desktop library for organizing books and the individual physical copies you own or sell. The desktop library is the authoritative record; the mobile companion sends captures to it."),
        ("bullet", "Bibliographic record", "describes a title or edition and can be shared by several copies."),
        ("bullet", "Physical copy", "has its own Copy ID, photograph, format, condition, location, price, and inventory status."),
        ("note", "Offline use", "Cataloging, inventory, sales, and reports use the local database. ISBN metadata lookup needs an internet connection when you request it."),
    )),
    ("Acquisitions", "Adding books", (
        ("p", None, "You can enter book details yourself or use an ISBN lookup to suggest metadata. Check every suggested value before saving; provider records can be incomplete or describe a different edition."),
        ("steps", None, (
            ("Open the form.", "Choose Acquisitions and Add a book, Catalog and Add Book, or Dashboard and Add a book."),
            ("Enter the book details.", "Title, Author, and Genre are required. ISBN, publisher, year, edition, page count, SRP, and synopsis are optional."),
            ("Enter copy details.", "Format, Condition, Location, Price in the selected currency, and a readable Copy Photo are required. Choose Photo to select the image. Location starts at Not Specified."),
            ("Review and save.", "Correct any red field message, then choose Save Book. Your entered details remain in the form if validation fails."),
        )),
        ("bullet", "ISBN lookup", "Enter an ISBN and choose Look Up ISBN. Returned metadata fills empty fields and leaves your existing entries in place. Lookup is optional; manual entry is supported."),
    )),
    ("Catalog", "Catalog and Inventory", (
        ("p", None, "Catalog presents one photo card for each active physical copy. Inventory presents the same copies in a sortable table."),
        ("bullet", "Find copies", "Use the search box and Genre, Condition, Location, and Status filters. Catalog sorts by Title, Copy ID, or Price; use the adjacent arrow to switch between ascending and descending order. Inventory sorts by its column headings."),
        ("bullet", "Edit a copy", "Double-click a row in Inventory, or choose Edit Book from a copy's Catalog context menu. Changes apply to that physical copy."),
        ("bullet", "Separate copies", "Adding another copy of the same ISBN reuses its bibliographic record after confirmation. A different ISBN remains a separate record, even when title and author match."),
        ("note", "Copy status", "Available, Listed, Not for Sale, and Sold belong to individual copies. Sold copies remain in inventory and history."),
    )),
    ("Sale History", "Sales and reports", (
        ("steps", None, (
            ("Select a copy.", "In Catalog or Inventory, open its context menu."),
            ("Record a sale.", "Choose Mark as Sold. BookLedger records the current Price and today's local date."),
            ("Reverse a sale.", "Change a Sold copy to another status and choose a reason. The original sale remains in Sale History as a reversed event."),
        )),
        ("bullet", "Sale History", "Lists completed and reversed sale events. Reversed sales remain visible but are excluded from sales revenue."),
        ("bullet", "Reports", "Inventory Summary counts active copies and titles. Inventory Valuation uses copy prices; Expected Revenue includes Available and Listed copies; Sales Revenue uses completed sale events."),
        ("bullet", "Dashboard", "Shows copy and title counts by status and recently added copies."),
    )),
    ("Settings", "Settings and customization", (
        ("p", None, "Open Settings and choose Preferences to customize lists and appearance. Changes to a configured value affect the choices available for future edits."),
        ("bullet", "Genre and Format", "Add or rename values in Preferences. A value assigned to copies cannot be deleted; update those copies or rename the value to move the assignments."),
        ("bullet", "Location", "Not Specified is a fixed system default and cannot be renamed or removed. Add and rename other locations in Preferences. A location assigned to a copy cannot be deleted."),
        ("bullet", "Shop logo", "Change Logo selects the configurable shop image, and Add Logo Link sets its click-through address. Clear Logo removes that customization."),
        ("note", "Application branding", "The BookLedger banner and application identity are part of the app. They are separate from the configurable shop logo."),
        ("bullet", "Theme", "Choose one of the themes available in the installed Tk runtime, then select Apply."),
    )),
    ("Settings", "Metadata and ISBN lookup", (
        ("p", None, "ISBN lookup queries the enabled providers in the order shown in Settings, Metadata Sources. Later providers can fill supported fields that earlier results left empty. Your manually entered values are preserved."),
        ("bullet", "Open Library", "Can return title, author, genre, publisher, publication year, edition, and page count."),
        ("bullet", "Google Books", "Can return title, author, genre, synopsis, publisher, publication year, and page count."),
        ("bullet", "Archive.org", "Can return title, author, synopsis, publisher, publication year, and edition."),
        ("bullet", "Booktopia", "Can return title, author, synopsis, publisher, publication year, edition, page count, and format."),
        ("bullet", "Bigbook", "Can return title, author, verified ISBN, synopsis, publication year, and page count."),
        ("bullet", "Hardcover", "Can return title, author, verified ISBN, genre, synopsis, publisher, publication year, edition, and page count."),
        ("note", "Provider order", "The default order is Open Library, Google Books, Archive.org, Hardcover, Booktopia, then Bigbook. Hardcover is enabled by default and requires a token in API Management; without one, lookup continues to the next provider. Bigbook starts disabled. Saved provider preferences are preserved."),
        ("bullet", "API Management", "Use Settings, API Management to show or hide, test, save, or remove credentials. Open Library, Archive.org, and Booktopia do not ask for a BookLedger API credential. Google Books accepts an optional key. Bigbook needs an API key and starts disabled. Hardcover is enabled by default and needs a personal token; missing credentials do not block later providers."),
        ("bullet", "Check a provider", "In Settings, use ISBN Lookup Test to select a provider, enter an ISBN, and inspect its result and field statuses. This tests that provider directly; it does not save a book."),
        ("bullet", "Review results", "Retrieved fields are suggestions. Confirm title, author, edition, and ISBN before saving. Unconfirmed ISBN results are not treated as verified matches."),
        ("note", "ISBN checks", "BookLedger checks ISBN-10 and ISBN-13 check digits. An invalid ISBN requires an explicit manual-entry override before saving."),
        ("warning", "Lookup problems", "No matching record or no data means the provider supplied no usable fields. Lookup failed can indicate a network, provider, credential, quota, or rate-limit problem. Check the ISBN and provider settings, try another enabled provider, or enter the details manually."),
    )),
    ("Settings", "Backup and restore", (
        ("p", None, "Backups are portable ZIP snapshots. They contain the database, managed copy and Trash photos, managed assets and posters, and application configuration. Activity logs, caches, and unrelated files are not included."),
        ("steps", None, (
            ("Create a backup.", "Open Settings, Storage and Backup, then choose Back Up Now. Keep the resulting ZIP in a safe location."),
            ("Restore a backup.", "Choose Restore Backup, select the ZIP, review the confirmation, and confirm only if you intend to replace the active library."),
        )),
        ("warning", "Restore replaces data", "BookLedger verifies the archive and creates a recovery backup before activation. Restore replaces the active database, photos, assets, and configuration; it does not merge libraries."),
        ("note", "Backup safety", "Archives are not encrypted and can contain configuration secrets. Protect backup files and keep one until you have confirmed the restored library."),
    )),
    ("About", "Statuses and messages", (
        ("bullet", "Inventory", "Available can be sold; Listed is listed for sale; Not for Sale is withheld from sale; Sold records a sale for that copy."),
        ("bullet", "Metadata", "The form can show Metadata retrieved, Partially retrieved, No matching ISBN record, Results returned but ISBN could not be confirmed, Record found but no usable supported metadata, or Metadata unavailable. Provider and field details explain which values were found."),
        ("bullet", "Mobile companion", "Not Paired means no device is registered. Paired - Connected means the paired phone confirmed its connection recently. Paired - Not Connected means no current confirmation is available. Receiving appears during an active transfer."),
        ("bullet", "Validation", "Required book fields are Title, Author, Genre, Format, Condition, Price, and Copy Photo. Red inline messages identify missing details, invalid configured values, or an invalid price. ISBN check-digit warnings can be overridden for manual entry; photo messages ask for a readable image."),
        ("note", "Colors vary by area", "Inventory uses green for Available, red for Sold, and neutral gray for Listed or Not for Sale. The mobile indicator uses green for Paired - Connected, amber for Paired - Not Connected and Receiving, red for a desktop service error, and gray for Not Paired. In ISBN Lookup Test, green OK means a field was returned; gray means No Data, N/A, or not checked. Its response time is green at 3 seconds or less and red when slower. Other status messages use green for success and red for errors; amber is used for a warning such as Receiving."),
    )),
    ("About", "Mobile companion", (
        ("p", None, "The Android companion captures ISBNs and cover photographs, then transfers those captures over your local network to BookLedger Desktop. It does not edit the library or replace desktop cataloging. Pair only on a trusted network because connection traffic uses unencrypted HTTP."),
        ("steps", None, (
            ("Pair the phone.", "Open Settings and Mobile App Setup on the desktop. Scan its QR code, or enter the desktop's local IPv4 address, port, and temporary pairing code in Pair / Connect on Android."),
            ("Capture one book.", "Choose Single Entry. Scan a barcode, enter an ISBN manually, or choose No ISBN. Save the identifier, photograph the front cover, and choose Save. Use Retake if the photo needs replacing."),
            ("Send the capture.", "When the capture is ready and the phone is connected, choose Send. A failed transfer leaves the capture on the phone so you can reconnect and retry."),
            ("Capture a batch.", "Choose Bulk Entry and set a queue size from 5 to 20. Identify and photograph each book, then choose Queue. The queue can be sent when full; hold Queue to finish a smaller batch early, then choose Send."),
        )),
        ("bullet", "Desktop cataloging", "After receipt, BookLedger opens one Add Book form at a time in the batch sequence. Review the ISBN and staged photo, complete required catalog and copy details, and save each book before the next capture opens. You can discard the current capture or cancel its form; other captures remain queued."),
        ("bullet", "Transfer recovery", "An incomplete transfer retains unacknowledged captures on the phone for retry. The desktop stages received batches and resumes cataloging after a restart. If desktop photo recovery is reported, use Settings, Storage and Backup, Retry Recovery, then restart BookLedger."),
        ("bullet", "Connection states", "Android shows Not paired, Pairing, Connecting, Connected, Disconnected, Desktop unavailable, Pairing rejected, Pairing no longer valid, or Connection error. The desktop indicator shows Not Paired, Paired - Connected, or Paired - Not Connected. Connected requires an authenticated confirmation within the last 45 seconds; Receiving marks an active incoming transfer. Mobile App Setup separately shows Starting local service, Ready for pairing, Service error, Stopping, or Service inactive."),
        ("warning", "If pairing or sending fails", "Confirm BookLedger Desktop is open and Mobile App Setup says Ready for pairing or Paired, both devices can reach each other on the same trusted local network, and the temporary pairing code has not expired. Try QR pairing or enter the desktop's private IPv4 address and port manually. Check that the local firewall permits BookLedger on the trusted network. If already paired, choose Reconnect now; if pairing was revoked, pair again. Keep Android open until receipt is confirmed; bulk captures are held in a session queue."),
        ("note", "Capture limits", "Single and bulk captures contain an optional ISBN and a front-cover photo. The Android companion is a capture and transfer tool; book details, copy condition, location, price, and final saving are handled in the desktop form."),
    )),
    ("About", "Data and moving between computers", (
        ("p", None, "The local SQLite database is the source of truth for bibliographic records, copies, status, and sales. Managed copy photographs, Trash photographs, and assets are stored with BookLedger's local data."),
        ("bullet", "Configuration", "Application preferences, provider order, and API credentials are stored in the BookLedger configuration. Protect the configuration and backups that contain credentials."),
        ("steps", None, (
            ("Back up the current computer.", "Choose Back Up Now and copy the resulting BookLedger ZIP to a USB drive or other portable storage."),
            ("Restore on the other computer.", "Open Settings, Storage and Backup, select Restore Backup, choose that ZIP, and confirm replacement."),
            ("Move work back later.", "Create a new backup on the computer currently in use, then restore that newer ZIP on the original computer."),
        )),
        ("warning", "No library merge", "Restore replaces the destination computer's active library. It does not combine edits from two computers. Keep the backups until you have checked the restored library."),
    )),
)

THEME_OPTIONS = (
    ("Clam", "clam"),
    ("Flatly", "flatly"),
    ("Light", "bootstrap-light"),
    ("Dark", "bootstrap-dark"),
)


def default_theme_name(available, current=""):
    """Prefer Clam for new defaults while retaining safe runtime fallbacks."""
    available = tuple(available)
    for name in ("clam", "flatly"):
        if name in available:
            return name
    if current in available:
        return current
    return available[0] if available else ""


def resolve_theme_name(available, configured, default):
    """Return a configured theme only when the active Tk runtime provides it."""
    available = tuple(available)
    if configured in available:
        return configured
    if default in available:
        return default
    return available[0] if available else ""


def available_theme_options(ttkbootstrap_names, native_names):
    """Return friendly choices supported by their respective style engines."""
    ttkbootstrap_names = {str(name) for name in ttkbootstrap_names}
    native_names = {str(name) for name in native_names}
    return tuple(
        (label, name)
        for label, name in THEME_OPTIONS
        if (name in native_names if name == "clam" else name in ttkbootstrap_names)
    )


def apply_theme_to_style(style, name):
    """Apply native Clam through Tk, and Bootstrap themes through ttkbootstrap."""
    if name == "clam":
        # Bypass ttkbootstrap.Style.theme_use: Clam has no ttkbootstrap
        # ThemeDefinition and passing it through that method corrupts its
        # current-theme state. The base method changes only Tk's active theme.
        return ttk.Style.theme_use(style, name)
    return style.theme_use(name)


try:
    import ttkbootstrap as tb
    _WindowBase = tb.Window
    _HAS_TTKBOOTSTRAP = True
except ImportError:
    _WindowBase = tk.Tk
    _HAS_TTKBOOTSTRAP = False


class BookLedgerApp(_WindowBase):
    def __init__(self, paths: AppPaths | None = None):
        if _HAS_TTKBOOTSTRAP:
            super().__init__(themename="flatly")
        else:
            super().__init__()
        apply_application_icon(self)
        self._mousewheel_router = MouseWheelRouter(self)
        self.paths = paths or AppPaths()
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
        self.mobile_incoming_store = MobileIncomingStore(self.db, self.paths.data)
        self.mobile_incoming_store.recover()
        self._incoming_catalog_batch = None
        self._incoming_reception_active = False
        self._mobile_indicator_refresh_pending = threading.Event()
        self._mobile_indicator_refresh_pending.set()
        self._mobile_indicator_polling = True
        self._mobile_indicator_last_connected = None
        self._catalog_action_buttons = []
        self._catalog_action_states = {}
        self.mobile_connection_service = MobileConnectionService(
            self.config_store,
            incoming_store=self.mobile_incoming_store,
            on_reception_change=self._queue_reception_state,
            on_batch_ready=self._queue_incoming_batch,
            on_activity=self._record_mobile_activity,
            on_state_change=self._queue_mobile_indicator,
        )
        self.mobile_activity_store = MobileActivityStore(self.db)
        self._configuration_warnings = self.config_store.migrate_legacy_settings(
            self.db,
            self.paths.google_books_config,
            self.paths._profile_google_books_config(),
        )
        # ttkbootstrap.Window owns a process-wide Style singleton. Keep that
        # instance, but list native Clam separately from its theme definitions.
        self.theme_style = self.style if _HAS_TTKBOOTSTRAP else ttk.Style(self)
        ttkbootstrap_themes = self.theme_style.theme_names()
        native_themes = ttk.Style(self).theme_names()
        self._theme_options = available_theme_options(ttkbootstrap_themes, native_themes)
        self._available_theme_names = tuple(name for _label, name in self._theme_options)
        self._theme_name_by_label = {label: name for label, name in self._theme_options}
        self._theme_label_by_name = {name: label for label, name in self._theme_options}
        current_theme = self.theme_style.theme_use() or ""
        default_theme = default_theme_name(self._available_theme_names, current_theme)
        defaults = ProviderSettings.defaults().to_document({
            "api_keys": {"google_books": ""},
            "logging": {"enabled": False},
            "preferences": {"theme": default_theme, "currency": "PHP"},
        })
        self._configuration_warnings += self.config_store.ensure_defaults(defaults)
        self.currency_service = CurrencyService(self.db, ExchangeRateService(self.db), None, self.config_store)
        self.currency = self.currency_service.reconcile()
        if self.currency_service.warning:
            self._configuration_warnings += (self.currency_service.warning,)
        configured_theme = self.config_store.get(("preferences", "theme"), default_theme)
        self._active_theme = resolve_theme_name(
            self._available_theme_names, configured_theme, default_theme
        )
        self._theme_startup_warning = ""
        if configured_theme == "clam" and "clam" not in self._available_theme_names:
            active_label = self._theme_label_by_name.get(self._active_theme, self._active_theme)
            self._theme_startup_warning = (
                f"Saved theme 'Clam' is unavailable in this Tk installation; using '{active_label}'."
            )
        if self._active_theme:
            try:
                apply_theme_to_style(self.theme_style, self._active_theme)
            except Exception as exc:
                self._theme_startup_warning = (
                    f"Could not apply saved theme '{self._theme_label_by_name.get(self._active_theme, self._active_theme)}': {exc}"
                )
                self._active_theme = current_theme or default_theme
                try:
                    apply_theme_to_style(self.theme_style, self._active_theme)
                except Exception:
                    pass
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
            self._log_event("application_started")
        self.reports = ReportService(self.db)
        self.photos = PhotoService(self.paths.photos, self.paths.trash)
        self.lifecycle = CopyLifecycleService(self.db, self.paths.data)
        self.verifier = VerificationService(self.db, self.paths.data)
        self.backups = BackupService(self.db, self.paths.data, self.paths.backups, self.paths.provider_config)
        self.currency_service.backup = self.backups
        self.posters = PosterService(self.db, self.paths, currency=lambda: self.currency)
        self.metadata_lookup = MetadataLookupService(
            build_providers(self.provider_settings, credentials=self._load_api_credentials())
        )
        self.title(f"{APP_NAME} · Book collection manager")
        self.geometry("1280x800")
        self.minsize(1000, 650)
        self._configure_style()
        self._build_shell()
        self.show_page("Dashboard")
        self.mobile_connection_service.start()
        self._poll_mobile_indicator()
        self.after(0, self._resume_mobile_incoming)
        self.protocol("WM_DELETE_WINDOW", self._close_application)
        self.report_callback_exception = self._report_callback_exception
        self.bind_all("<Control-n>", lambda _e: self.open_add_form())
        self.bind_all("<Control-f>", lambda _e: self.search_entry.focus_set())
        self.bind_all("<F5>", lambda _e: self.refresh_current())

    def _configure_style(self):
        style = self.theme_style
        if style.theme_use() == "clam":
            def configure(style_name, **options):
                return ttk.Style.configure(style, style_name, **options)
        else:
            configure = style.configure

        configure("Treeview", rowheight=30, font=("Segoe UI", 10), borderwidth=0)
        configure("Treeview.Heading", font=("Segoe UI", 10, "bold"), padding=8)
        configure("Sidebar.TButton", anchor="w", padding=(14, 4), font=("Segoe UI", 10))
        configure("SidebarActive.TButton", anchor="w", padding=(14, 4), font=("Segoe UI", 10, "bold"))
        configure("Primary.TButton", padding=(12, 8), font=("Segoe UI", 10, "bold"))
        configure("Invalid.TEntry", fieldbackground="#fff0f0")
        configure("Invalid.TCombobox", fieldbackground="#fff0f0")

    def _apply_theme_selection(self):
        selected_label = str(self.theme_var.get() or "")
        selected = self._theme_name_by_label.get(selected_label, "")
        if selected not in self._available_theme_names:
            self.status_var.set("Choose a supported theme from the list.")
            return False

        previous = self.theme_style.theme_use()
        if selected == previous:
            return True
        try:
            apply_theme_to_style(self.theme_style, selected)
            self._configure_style()
            self.config_store.set(("preferences", "theme"), selected)
        except Exception as exc:
            self._log_event("theme_change_failed")
            try:
                apply_theme_to_style(self.theme_style, previous)
                self._configure_style()
            except Exception:
                pass
            self.theme_var.set(self._theme_label_by_name.get(previous, previous))
            self.status_var.set(f"Could not apply theme: {exc}")
            return False

        self._active_theme = selected
        self._log_event("theme_changed")
        self.status_var.set(f"Theme '{selected_label}' applied and saved.")
        return True

    def _build_shell(self):
        shell = ttk.Frame(self)
        shell.pack(fill="both", expand=True)
        self.sidebar = ttk.Frame(shell, padding=(12, 10), width=210)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        brand = ttk.Frame(self.sidebar)
        brand.pack(fill="x", pady=(0, 8))
        self._application_banner_image = None
        try:
            with Image.open(resource_path("assets", "banner.png")) as source:
                banner = source.convert("RGB")
                banner.thumbnail((186, 62), Image.Resampling.LANCZOS)
                self._application_banner_image = ImageTk.PhotoImage(banner, master=self)
        except (OSError, ValueError, Image.DecompressionBombError):
            pass
        ttk.Label(
            brand,
            image=self._application_banner_image or "",
            text="BookLedger" if self._application_banner_image is None else "",
            font=("Segoe UI", 17, "bold"),
        ).pack(anchor="w")
        ttk.Separator(self.sidebar).pack(fill="x", pady=(0, 6))
        self.nav_buttons = {}
        self._nav_image_sets = {}
        for name, icon_file, fallback in NAVIGATION_ITEMS:
            icon_path = resource_path("assets", icon_file)
            images = []
            if icon_path.is_file():
                for visible_size in NAV_ICON_CONTENT_SIZES:
                    raster = render_svg_icon(icon_path, frame_size=NAV_ICON_FRAME_SIZE, content_size=visible_size)
                    if raster is not None:
                        images.append(ImageTk.PhotoImage(raster, master=self))
            self._nav_image_sets[name] = tuple(images)
            button = ttk.Button(
                self.sidebar,
                text=name,
                image=images[0] if images else "",
                compound="left" if images else "none",
                style="Sidebar.TButton",
                command=lambda selected=name: self.show_page(selected),
            )
            if not images:
                button.configure(text=f"{fallback}   {name}")
            button.pack(fill="x", pady=1)
            self.nav_buttons[name] = button
            button._nav_frame_images = tuple(images)
            button._nav_frame_index = 0
            button._nav_animation_after_id = None
            if images:
                button.bind("<Enter>", lambda _event, target=button: self._animate_navigation_button(target, 2))
                button.bind("<Leave>", lambda _event, target=button: self._animate_navigation_button(target, 0))
            help_text = NAVIGATION_TOOLTIPS[name]
            button.bind("<Enter>", lambda event, message=help_text: self._show_hover_tooltip(event, message), add="+")
            button.bind("<Leave>", self._hide_hover_tooltip, add="+")
        ttk.Frame(self.sidebar).pack(fill="both", expand=True)
        footer = ttk.Frame(self.sidebar)
        footer.pack(fill="x")
        self._build_sidebar_footer(footer)

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
        self.status_var = tk.StringVar(value=self._theme_startup_warning or "Ready")
        self.status_label = ttk.Label(right, textvariable=self.status_var, anchor="w")
        self.status_label.pack(fill="x", pady=(12, 0))
        self._bind_status_color(self.status_var, self.status_label)

    def _build_sidebar_footer(self, footer):
        self._brand_image = None
        self.brand_logo_label = ttk.Label(footer, cursor="hand2")
        self.brand_logo_label.bind("<Button-1>", lambda _event: self._open_shop_link())
        self.brand_logo_label.pack(anchor="w", pady=(0, 8))
        self._refresh_brand_logo()
        self.mobile_connection_status_var = tk.StringVar()
        self.mobile_connection_status_label = ttk.Label(footer, textvariable=self.mobile_connection_status_var, foreground=NEUTRAL_COLOR)
        self.mobile_connection_status_label.pack(anchor="w", pady=(0, 5))
        ttk.Label(footer, text=f"Version {__version__}", foreground="#64748b", font=("Segoe UI", 9)).pack(anchor="w")
        self._update_mobile_connection_indicator()

    @staticmethod
    def _bind_status_color(variable, label):
        def update_color(*_args):
            label.configure(foreground=status_message_color(variable.get()))

        variable.trace_add("write", update_color)
        update_color()

    def _refresh_brand_logo(self):
        configured = self.config_store.get(("preferences", "shop_logo_path"), "")
        selected = resolve_managed_logo(self.paths.data, configured)
        self._brand_image = None
        if selected is not None and selected.is_file():
            try:
                with Image.open(selected) as source:
                    image = source.convert("RGBA")
                    image.thumbnail((176, 66), Image.Resampling.LANCZOS)
                    self._brand_image = ImageTk.PhotoImage(image, master=self)
            except (OSError, ValueError, Image.DecompressionBombError):
                self._brand_image = None

        if self._brand_image is None:
            self.brand_logo_label.configure(image="")
            if not self.brand_logo_label.winfo_manager():
                self.brand_logo_label.pack(anchor="w", pady=(0, 8))
        else:
            self.brand_logo_label.configure(image=self._brand_image)
            if not self.brand_logo_label.winfo_manager():
                self.brand_logo_label.pack(anchor="w", pady=(0, 8))

    def _animate_navigation_button(self, button, target_index):
        try:
            after_id = getattr(button, "_nav_animation_after_id", None)
            if after_id is not None:
                self.after_cancel(after_id)
            current_index = int(getattr(button, "_nav_frame_index", 0))
            images = button._nav_frame_images
            if not images or current_index == target_index:
                button._nav_animation_after_id = None
                return

            direction = 1 if target_index > current_index else -1

            def advance():
                if not button.winfo_exists():
                    return
                next_index = int(button._nav_frame_index) + direction
                button.configure(image=images[next_index])
                button._nav_frame_index = next_index
                if next_index == target_index:
                    button._nav_animation_after_id = None
                else:
                    button._nav_animation_after_id = self.after(32, advance)

            button._nav_animation_after_id = self.after(1, advance)
        except (AttributeError, tk.TclError):
            return

    def _update_active_navigation(self):
        for name, button in getattr(self, "nav_buttons", {}).items():
            button.configure(style="SidebarActive.TButton" if name == self.current_page else "Sidebar.TButton")

    def _logo_url(self):
        value = self.config_store.get(("preferences", "shop_url"), "")
        return normalize_shop_url(value)

    def _open_shop_link(self):
        url = self._logo_url()
        if not url:
            return False
        if url is None:
            self.status_var.set("Shop link is invalid; use an HTTP or HTTPS URL.")
            return False
        try:
            return bool(webbrowser.open(url, new=2))
        except (OSError, webbrowser.Error):
            self.status_var.set("Could not open the shop link.")
            return False

    def _save_shop_url(self):
        url = normalize_shop_url(self.shop_url_var.get())
        if url is None:
            self.status_var.set("Enter a valid HTTP or HTTPS shop URL.")
            return False
        try:
            previous = self.config_store.get(("preferences", "shop_url"), "")
            self.config_store.set(("preferences", "shop_url"), url)
        except (OSError, ValueError, sqlite3.Error) as exc:
            self._log_event("shop_link_change_failed")
            self.status_var.set(f"Could not save shop link: {exc}")
            return False
        self.shop_url_var.set(url)
        if previous != url:
            self._log_event("shop_link_changed")
        self.status_var.set("Shop link saved." if url else "Shop link cleared.")
        return True

    def _change_shop_logo(self):
        selected = filedialog.askopenfilename(
            parent=self,
            title="Choose Shop Logo",
            filetypes=(("Image files", "*.png *.jpg *.jpeg *.gif *.bmp *.webp *.tif *.tiff"), ("All files", "*.*")),
        )
        if not selected:
            return False
        old_reference = self.config_store.get(("preferences", "shop_logo_path"), "")
        stored_path = None
        try:
            stored_path = store_shop_logo(selected, self.paths.assets)
            reference = stored_path.relative_to(self.paths.data.resolve()).as_posix()
            self.config_store.set(("preferences", "shop_logo_path"), reference)
            self._refresh_brand_logo()
        except (OSError, ValueError, sqlite3.Error, Image.DecompressionBombError) as exc:
            self._log_event("shop_logo_change_failed")
            if stored_path is not None:
                try:
                    if self.config_store.get(("preferences", "shop_logo_path"), "") != stored_path.relative_to(self.paths.data.resolve()).as_posix():
                        stored_path.unlink(missing_ok=True)
                except (OSError, ValueError):
                    pass
            messagebox.showerror("Could not change logo", str(exc), parent=self)
            return False
        self.status_var.set("Shop logo updated.")
        if old_reference != reference:
            self._log_event("shop_logo_changed")
        if old_reference and old_reference != reference:
            remove_obsolete_shop_logo(self.paths.data, old_reference)
        return True

    def _clear_shop_logo(self):
        """Restore the bundled logo and retire only the old managed custom logo."""
        old_reference = self.config_store.get(("preferences", "shop_logo_path"), "")
        try:
            self.config_store.set(("preferences", "shop_logo_path"), "")
            self._refresh_brand_logo()
        except (OSError, ValueError, sqlite3.Error) as exc:
            self._log_event("shop_logo_remove_failed")
            self.status_var.set(f"Could not clear shop logo: {exc}")
            return False
        self.status_var.set("Default shop logo restored.")
        if old_reference:
            self._log_event("shop_logo_removed")
        remove_obsolete_shop_logo(self.paths.data, old_reference)
        return True

    def _clear_shop_url(self):
        """Clear the saved shop link and its visible entry."""
        try:
            previous = self.config_store.get(("preferences", "shop_url"), "")
            self.config_store.set(("preferences", "shop_url"), "")
        except (OSError, ValueError, sqlite3.Error) as exc:
            self._log_event("shop_link_change_failed")
            self.status_var.set(f"Could not clear shop link: {exc}")
            return False
        self.shop_url_var.set("")
        if previous:
            self._log_event("shop_link_changed")
        self.status_var.set("Shop link cleared.")
        return True

    def _clear_workspace(self):
        # Destroyed page widgets must not remain the active source for a later event.
        layout_after_id = getattr(self, "_catalog_layout_after_id", None)
        if layout_after_id is not None:
            try:
                self.after_cancel(layout_after_id)
            except tk.TclError:
                pass
        self._catalog_layout_after_id = None
        self._catalog_pending_layout = None
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
        update_navigation = getattr(self, "_update_active_navigation", None)
        if update_navigation is not None:
            update_navigation()
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
        elif name == "About":
            self._build_about_page()
        else:
            self._build_settings()

    def _build_about_page(self):
        """Show the verified offline user guide in short, illustrated pages."""
        self.status_var.set("Ready")
        self.about_page_index = min(getattr(self, "about_page_index", 0), len(ABOUT_GUIDE_PAGES) - 1)
        ttk.Label(self.workspace, text="BookLedger User Guide", font=("Segoe UI", 16, "bold")).pack(anchor="w", pady=(0, 12))
        heading = ttk.Frame(self.workspace)
        heading.pack(fill="x", pady=(0, 10))
        self.about_icon_label = ttk.Label(heading)
        self.about_icon_label.pack(side="left", padx=(0, 10))
        self.about_heading_label = ttk.Label(heading, font=("Segoe UI", 14, "bold"))
        self.about_heading_label.pack(side="left", anchor="center")
        self.about_page_count = ttk.Label(heading, foreground="#64748b")
        self.about_page_count.pack(side="right", anchor="center")
        frame = ttk.Frame(self.workspace)
        actions = ttk.Frame(self.workspace)
        actions.pack(fill="x", side="bottom", pady=(10, 0))
        navigation = ttk.Frame(actions)
        navigation.pack(anchor="center")
        self.about_back_button = ttk.Button(navigation, text="Back", command=lambda: self._show_about_manual_page(self.about_page_index - 1))
        self.about_back_button.pack(side="left", padx=(0, 8))
        self.about_next_button = ttk.Button(navigation, text="Next", command=lambda: self._show_about_manual_page(self.about_page_index + 1))
        self.about_next_button.pack(side="left", padx=(8, 0))
        frame.pack(fill="both", expand=True)
        text = tk.Text(frame, wrap="word", height=18, relief="flat", borderwidth=0, padx=18, pady=12, font=("Segoe UI", 11), spacing1=3, spacing3=8)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)
        text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        text.tag_configure("body", font=("Segoe UI", 11), foreground="#1f2937", lmargin1=10, lmargin2=28, spacing3=9)
        text.tag_configure("strong", font=("Segoe UI", 11, "bold"), foreground="#173b63")
        text.tag_configure("bullet", lmargin1=18, lmargin2=38, spacing3=7)
        text.tag_configure("steps", lmargin1=22, lmargin2=48, spacing3=7)
        text.tag_configure("note", foreground="#245b9e", background="#edf5ff", lmargin1=12, lmargin2=30, spacing1=5, spacing3=10)
        text.tag_configure("warning", foreground=ERROR_COLOR, background="#fff1f0", lmargin1=12, lmargin2=30, spacing1=5, spacing3=10)
        text.tag_raise("note", "strong")
        text.tag_raise("warning", "strong")
        self.about_text = text
        self._show_about_manual_page(self.about_page_index)
        wheel_router = getattr(self, "_mousewheel_router", None)
        if wheel_router is not None:
            wheel_router.register(text, frame)

    def _show_about_manual_page(self, index):
        self.about_page_index = max(0, min(index, len(ABOUT_GUIDE_PAGES) - 1))
        icon_page, heading, paragraphs = ABOUT_GUIDE_PAGES[self.about_page_index]
        images = getattr(self, "_nav_image_sets", {}).get(icon_page, ())
        self.about_icon_label.configure(image=images[0] if images else "")
        self.about_heading_label.configure(text=heading)
        self.about_page_count.configure(text=f"{self.about_page_index + 1} of {len(ABOUT_GUIDE_PAGES)}")
        self.about_text.configure(state="normal")
        self.about_text.delete("1.0", "end")
        for block in paragraphs:
            BookLedgerApp._insert_about_manual_block(self.about_text, block)
        self.about_text.configure(state="disabled")
        self.about_back_button.configure(state="normal" if self.about_page_index else "disabled")
        self.about_next_button.configure(state="normal" if self.about_page_index < len(ABOUT_GUIDE_PAGES) - 1 else "disabled")

    @staticmethod
    def _insert_about_manual_block(text, block):
        kind, heading, content = block
        if kind in {"steps", "bullets"}:
            tag = "steps" if kind == "steps" else "bullet"
            for index, (label, detail) in enumerate(content, start=1):
                marker = f"{index}.  " if kind == "steps" else "•  "
                text.insert("end", marker, tag)
                text.insert("end", f"{label} ", (tag, "strong"))
                text.insert("end", f"{detail}\n\n", (tag, "body"))
            return
        tag = "warning" if kind == "warning" else "note" if kind == "note" else "body"
        if kind == "bullet":
            text.insert("end", "•  ", "bullet")
            tag = "bullet"
        if heading:
            text.insert("end", f"{heading} ", (tag, "strong"))
        text.insert("end", f"{content}\n\n", tag)

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
        self._catalog_action_button(actions, text="＋  Add a book", style="Primary.TButton", command=self.open_add_form).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Open catalog", command=lambda: self.show_page("Catalog")).pack(side="left", padx=8)
        ttk.Button(actions, text="Open Poster Folder", command=self._open_poster_folder).pack(side="left", padx=8)
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
        self._catalog_action_button(top, text="＋ Add Book", style="Primary.TButton", command=self.open_add_form).pack(side="right")
        filters = ttk.Frame(self.workspace)
        filters.pack(fill="x", pady=(0, 12))
        self.genre_filter = tk.StringVar(value="All")
        self.condition_filter = tk.StringVar(value="All")
        self.location_filter = tk.StringVar(value="All")
        self.status_filter = tk.StringVar(value="All")
        locations = self.catalog.list_locations()
        filter_specs = (
            ("Genre", self.genre_filter, ("All",) + self.catalog.list_genres(), 18),
            ("Condition", self.condition_filter, ("All",) + BOOK_CONDITIONS, 12),
            ("Location", self.location_filter, ("All",) + locations, 14),
            ("Status", self.status_filter, ("All",) + COPY_STATUSES, 12),
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
            self._catalog_action_button(top, text="Edit Selected", command=self.open_selected_edit).pack(side="right", padx=(0, 8))
            self._make_tree(frame, columns=("code", "copy_number", "title", "author", "genre", "format", "condition", "location", "price", "status"), headings=("Copy ID", "Copy #", "Title", "Author", "Genre", "Format", "Condition", "Location", f"Price ({self.currency})", "Status"), height=18)
            self._inventory_status_tags = {}
            for status, color in INVENTORY_STATUS_COLORS.items():
                tag = f"inventory_status_{status.casefold().replace(' ', '_')}"
                self.tree.tag_configure(tag, foreground=color)
                self._inventory_status_tags[status] = tag
            self.tree.bind("<Double-1>", self._on_tree_double_click)
            self.tree.bind("<Button-3>", self._on_inventory_right_click)
            for col in self.tree["columns"]:
                self.tree.heading(col, command=lambda c=col: self._sort_inventory(c))
        else:
            sort_bar = ttk.Frame(frame)
            sort_bar.pack(fill="x", pady=(0, 8))
            ttk.Label(sort_bar, text="Sort by").pack(side="left")
            self.catalog_sort = tk.StringVar(value=getattr(self, "_catalog_sort_value", "Title"))
            sort_box = ttk.Combobox(sort_bar, textvariable=self.catalog_sort, values=("Title", "Copy ID", "Price"), state="readonly", width=12)
            sort_box.pack(side="left", padx=(6, 0))
            sort_box.bind("<<ComboboxSelected>>", self._catalog_sort_changed)
            descending = getattr(self, "_catalog_sort_descending", False)
            direction_button = ttk.Button(
                sort_bar,
                text="↓" if descending else "↑",
                width=3,
                command=self._toggle_catalog_sort_direction,
            )
            direction_button.pack(side="left", padx=(4, 0))
            self.catalog_sort_direction_button = direction_button
            self._add_hover_tooltip(direction_button, "Up arrow means ascending; down arrow means descending. Click to toggle.")
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
            value_key = {"code": "copy_code", "copy_number": "copy_number", "title": "title", "author": "author", "genre": "genre", "format": "format", "condition": "condition", "location": "location", "price": "display_price_minor", "status": "status"}.get(sort_column, "title")
            rows = self._sold_last_sort(rows, lambda row: row[value_key] or "", reverse)
            self._visible_rows = rows
            self.tree.delete(*self.tree.get_children())
            for row in rows:
                values = (row["copy_code"], row["copy_number"], combined_title(row["title"], row.get("subtitle")), row["author"], row["genre"], row["format"], row["condition"], row["location"], self.money(row["display_price_minor"]), row["status"])
                status_tags = getattr(self, "_inventory_status_tags", {})
                self.tree.insert("", "end", iid=str(row["copy_id"]), values=values, tags=(status_tags.get(row["status"], ""),))
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
        canvas = self.catalog_canvas
        cards = self.catalog_cards
        window = self._catalog_window
        wheel_router = getattr(self, "_mousewheel_router", None)
        if wheel_router is not None:
            wheel_router.register(canvas, parent)
        cards.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        self._catalog_card_widgets = []
        self._catalog_grid_columns = 0
        self._catalog_layout_after_id = None
        self._catalog_pending_layout = None

        def resize_canvas(_event):
            self._queue_catalog_layout(canvas)

        self.catalog_canvas.bind("<Configure>", resize_canvas)

    def _queue_catalog_layout(self, canvas):
        self._catalog_pending_layout = canvas
        if self._catalog_layout_after_id is None:
            self._catalog_layout_after_id = self.after_idle(self._apply_pending_catalog_layout)

    def _apply_pending_catalog_layout(self):
        self._catalog_layout_after_id = None
        canvas = self._catalog_pending_layout
        self._catalog_pending_layout = None
        if canvas is None:
            return
        if canvas is not getattr(self, "catalog_canvas", None):
            return
        try:
            if not canvas.winfo_exists():
                return
        except tk.TclError:
            return
        self._layout_catalog_cards(canvas.winfo_width())

    def _layout_catalog_cards(self, available_width):
        if not self._catalog_card_widgets:
            return
        cell_width = CATALOG_CARD_WIDTH + CATALOG_CARD_GAP
        columns = max(1, int(max(available_width, 1) // cell_width))
        content_width = max(max(available_width, 1), columns * cell_width)
        canvas = getattr(self, "catalog_canvas", None)
        window = getattr(self, "_catalog_window", None)
        if canvas is not None and window is not None:
            canvas.itemconfigure(window, width=content_width)
        prior_columns = self._catalog_grid_columns
        if columns == prior_columns:
            return
        for column in range(max(prior_columns, columns)):
            self.catalog_cards.grid_columnconfigure(column, weight=0, uniform="")
        self._catalog_grid_columns = columns
        for index, card in enumerate(self._catalog_card_widgets):
            card.grid(row=index // columns, column=index % columns, sticky="nw", padx=CATALOG_CARD_GAP // 2, pady=7)

    def _render_catalog_cards(self, rows):
        for child in self.catalog_cards.winfo_children():
            child.destroy()
        self._catalog_images = []
        self._catalog_card_widgets = []
        self._catalog_grid_columns = 0
        if not hasattr(self, "_catalog_title_font"):
            self._catalog_title_font = tkfont.Font(
                root=self, family="Segoe UI", size=10, weight="bold"
            )
        author_font_spec = ttk.Style(self).lookup("TLabel", "font") or "TkDefaultFont"
        if getattr(self, "_catalog_author_font_spec", None) != author_font_spec:
            self._catalog_author_font_spec = author_font_spec
            self._catalog_author_font = tkfont.Font(root=self, font=author_font_spec)
        title_area_height = self._catalog_two_line_height(
            self.catalog_cards, self._catalog_title_font, CATALOG_CARD_WIDTH - 40
        )
        author_area_height = self._catalog_two_line_height(
            self.catalog_cards, self._catalog_author_font, CATALOG_CARD_WIDTH - 40
        )
        for index, row in enumerate(rows):
            card = ttk.LabelFrame(self.catalog_cards, text=row["copy_code"], padding=8, width=CATALOG_CARD_WIDTH)
            self._catalog_card_widgets.append(card)
            art = tk.Frame(card, width=CATALOG_CARD_WIDTH - 40, height=180, background="#edf1f5")
            art.pack(fill="x", pady=(0, 7))
            art.pack_propagate(False)
            photo_path = Path(row["photo_path"])
            if not photo_path.is_absolute():
                photo_path = self.paths.data / photo_path
            try:
                photo = ImageTk.PhotoImage(self._load_catalog_thumbnail(photo_path, row["status"]))
                self._catalog_images.append(photo)
                image_label = tk.Label(art, image=photo, background="#edf1f5")
                image_label.place(relx=0.5, rely=0.5, anchor="center")
            except (OSError, tk.TclError):
                tk.Label(art, text="Photo Unavailable", background="#edf1f5", foreground="#596579").place(relx=0.5, rely=0.5, anchor="center")
            decoration = self._catalog_thumbnail_indicator(row["status"])
            if decoration == "sold":
                tk.Label(art, text="SOLD", bg="#b42318", fg="white", font=("Segoe UI", 12, "bold"), padx=10, pady=4).place(relx=0.5, rely=0.5, anchor="center")
            elif decoration == "lock":
                self._add_not_for_sale_lock(art)
            title = truncate_to_two_lines(
                catalog_display_title(row["title"], row.get("subtitle")),
                CATALOG_CARD_WIDTH - 40,
                self._catalog_title_font.measure,
            )
            self._catalog_text_block(
                card,
                title,
                self._catalog_title_font,
                CATALOG_CARD_WIDTH - 40,
                title_area_height,
            )
            ttk.Label(card, text=self._physical_copy_label(row), foreground="#596579").pack(anchor="w", pady=(2, 0))
            author = truncate_to_two_lines(
                row["author"], CATALOG_CARD_WIDTH - 40, self._catalog_author_font.measure
            )
            self._catalog_text_block(
                card,
                author,
                self._catalog_author_font,
                CATALOG_CARD_WIDTH - 40,
                author_area_height,
                foreground="#64748b",
                pady=(2, 5),
            )
            ttk.Label(card, text=self.money(row["display_price_minor"]), font=("Segoe UI", 11, "bold")).pack(anchor="w")
            def bind_card(widget, copy_id=row["copy_id"]):
                widget.bind("<Double-Button-1>", lambda _event: self.open_copy_details(copy_id))
                widget.bind("<Button-3>", lambda event: self.show_copy_context_menu(copy_id, event.x_root, event.y_root))
                for child in widget.winfo_children():
                    bind_card(child, copy_id)
            bind_card(card)
        for card in self._catalog_card_widgets:
            self._fix_catalog_card_geometry(card)
        self._queue_catalog_layout(self.catalog_canvas)

    @staticmethod
    def _catalog_two_line_height(parent, font, wraplength):
        probe = ttk.Label(
            parent,
            text="gypqj\ngypqj",
            font=font,
            wraplength=wraplength,
            anchor="nw",
            justify="left",
        )
        try:
            return max(font.metrics("linespace") * 2, probe.winfo_reqheight())
        finally:
            probe.destroy()

    @staticmethod
    def _catalog_text_block(
        parent, text, font, wraplength, height, *, foreground=None, pady=0
    ):
        area = ttk.Frame(parent, height=height)
        area.pack(fill="x", anchor="w", pady=pady)
        area.pack_propagate(False)
        label = ttk.Label(
            area,
            text=text,
            font=font,
            wraplength=wraplength,
            anchor="nw",
            justify="left",
            **({"foreground": foreground} if foreground else {}),
        )
        label.pack(fill="both", expand=True)
        return label

    @staticmethod
    def _fix_catalog_card_geometry(card):
        # Card contents use pack(), which otherwise overrides the configured width.
        card.update_idletasks()
        card.configure(width=CATALOG_CARD_WIDTH, height=card.winfo_reqheight())
        card.pack_propagate(False)

    @staticmethod
    def _add_not_for_sale_lock(parent):
        icon = tk.Canvas(parent, width=32, height=32, background="#edf1f5", highlightthickness=0, bd=0)
        icon.place(relx=1.0, x=-6, y=6, anchor="ne")
        icon.create_oval(1, 1, 31, 31, fill="#334155", outline="#ffffff", width=1)
        icon.create_arc(9, 6, 23, 20, start=0, extent=180, style="arc", outline="#ffffff", width=2)
        icon.create_rectangle(8, 14, 24, 25, fill="#ffffff", outline="#ffffff")
        icon.create_oval(14, 17, 18, 21, fill="#334155", outline="#334155")

    @staticmethod
    def _catalog_thumbnail_indicator(status):
        if status == "Sold":
            return "sold"
        if status == "Not for Sale":
            return "lock"
        return None

    def _sort_inventory(self, column):
        if getattr(self, "_inventory_sort_column", None) == column:
            self._inventory_sort_reverse = not getattr(self, "_inventory_sort_reverse", False)
        else:
            self._inventory_sort_column = column
            self._inventory_sort_reverse = False
        value_key = {"code": "copy_code", "copy_number": "copy_number", "title": "title", "author": "author", "genre": "genre", "format": "format", "condition": "condition", "location": "location", "price": "display_price_minor", "status": "status"}[column]
        self._visible_rows = self._sold_last_sort(self._visible_rows, lambda row: row[value_key] or "", self._inventory_sort_reverse)
        for index, row in enumerate(self._visible_rows):
            values = (row["copy_code"], row["copy_number"], combined_title(row["title"], row.get("subtitle")), row["author"], row["genre"], row["format"], row["condition"], row["location"], self.money(row["display_price_minor"]), row["status"])
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
    def _load_catalog_thumbnail(photo_path, status):
        with Image.open(photo_path) as source:
            image = source if source.mode == "RGB" else source.convert("RGB")
            image.load()
            image.thumbnail((CATALOG_CARD_WIDTH - 52, 170), Image.Resampling.LANCZOS)
            image = image.copy()
        return BookLedgerApp._sold_thumbnail(image, status)

    @staticmethod
    def _physical_copy_label(row):
        return f"Copy {row['copy_number']}"

    def _sort_catalog_rows(self, rows):
        return self._catalog_sort_rows(
            rows,
            self.catalog_sort.get(),
            getattr(self, "_catalog_sort_descending", False),
        )

    @staticmethod
    def _catalog_sort_rows(rows, field="Title", descending=False):
        key = {
            "Title": lambda row: row["title"].casefold(),
            "Copy ID": lambda row: int(row["copy_id"]),
            "Price": lambda row: int(row["display_price_minor"]),
        }.get(field, lambda row: row["title"].casefold())
        return sorted(
            rows,
            key=lambda row: (key(row), int(row["copy_id"])),
            reverse=descending,
        )

    def _catalog_sort_changed(self, _event=None):
        self._catalog_sort_value = self.catalog_sort.get()
        self._populate_catalog()

    def _toggle_catalog_sort_direction(self):
        self._catalog_sort_descending = not getattr(self, "_catalog_sort_descending", False)
        self.catalog_sort_direction_button.configure(
            text="↓" if self._catalog_sort_descending else "↑"
        )
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
        menu.add_command(
            label="Create Poster",
            state="disabled" if row["status"] == "Sold" else "normal",
            command=lambda cid=int(copy_id): self._create_poster(cid),
        )
        for status in ("Available", "Listed", "Not for Sale", "Sold"):
            menu.add_command(
                label=f"Mark as {status}",
                state="disabled" if row["status"] == status else "normal",
                command=lambda target=status, cid=copy_id: self._change_copy_status(cid, target),
            )
        menu.add_command(
            label="Edit Book",
            state="disabled" if getattr(self, "_incoming_reception_active", False) else "normal",
            command=lambda cid=copy_id: self.open_selected_edit(cid),
        )
        menu.add_command(label="Delete Book", command=lambda cid=copy_id: self._confirm_delete(cid))
        try:
            menu.tk_popup(x_root, y_root)
        finally:
            menu.grab_release()

    def _create_poster(self, copy_id):
        saved = create_poster_for_copy(
            self,
            service=self.posters,
            catalog=self.catalog,
            paths=self.paths,
            config_store=self.config_store,
            copy_id=int(copy_id),
            on_activity=lambda event, identifier: self._log_event(event, copy_id=identifier),
        )
        if saved and getattr(self, "current_page", None) in {"Catalog", "Inventory"}:
            self.refresh_current()
        return saved

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
            self._log_event("inventory_status_change_failed", copy_id=int(copy_id))
            messagebox.showerror("Status Change Failed", str(exc), parent=self)
            return
        self._after_save(f"{row['copy_code']} marked {target_status}.")
        event = "sale_recorded" if target_status == "Sold" else "sale_voided" if current == "Sold" else "inventory_status_changed"
        if hasattr(self, "_log_event"):
            self._log_event(event, copy_id=int(copy_id))

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
            except Exception as exc:
                self._log_event("copy_trash_failed", copy_id=int(copy_id))
                messagebox.showerror("Delete Failed", f"The copy was not safely moved to Trash: {exc}", parent=self)
                return
            self._log_event("copy_moved_to_trash", copy_id=int(copy_id))
            self._after_save(f"{row['copy_code']} moved to Trash.")

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
        self._catalog_action_button(panel, text="＋  Add a book", style="Primary.TButton", command=self.open_add_form).pack(anchor="w")
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
        canvas.create_text(12, (top + bottom) / 2, text=f"Revenue ({self.currency})", angle=90, fill="#334155", font=("Segoe UI", 9, "bold"))

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
        wheel_router = getattr(self, "_mousewheel_router", None)
        if wheel_router is not None:
            wheel_router.register(canvas, chart_frame)
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
        panel = MobileAppSetupPanel(
            parent,
            self.mobile_connection_service,
            self.mobile_activity_store,
            on_export_apk=self.export_apk,
        )
        panel.pack(fill="both", expand=True)
        self._mobile_app_setup_panel = panel
        return panel

    def _build_metadata_sources(self, parent):
        parent.columnconfigure(0, weight=3, uniform="metadata")
        parent.columnconfigure(1, weight=2, uniform="metadata")
        parent.rowconfigure(0, weight=1)

        panel = ttk.LabelFrame(parent, text="Metadata Sources", padding=12)
        panel.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        ttk.Label(panel, text="Enabled sources are searched from top to bottom. Drag a source by its handle to change priority.", wraplength=560).pack(anchor="w")
        self._provider_rows = {}
        self._provider_variables = {}
        provider_tooltips = {
            "open_library": "Public ISBN metadata lookup. The source is queried first by default.",
            "google_books": "Google Books may supply bibliographic fields and Book Details.",
            "archive_org": "Archive.org verifies candidate items individually and may supply bibliographic metadata and descriptions.",
            "booktopia": "Booktopia can enrich missing fields from its product pages.",
            "bigbook": "Bigbook uses the saved API key for exact ISBN searches and confirms an ISBN from book details before accepting fields.",
            "hardcover": "Hardcover uses the saved personal token to query editions by exact ISBN. Its API is in beta.",
        }
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
            name.bind("<Enter>", lambda event, help_text=provider_tooltips.get(descriptor.id, "Metadata provider."): self._show_hover_tooltip(event, help_text))
            name.bind("<Leave>", self._hide_hover_tooltip)
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
        self._provider_config_status_label = ttk.Label(panel, textvariable=self._provider_config_status, wraplength=560)
        self._provider_config_status_label.pack(anchor="w", pady=(8, 0))
        self._bind_status_color(self._provider_config_status, self._provider_config_status_label)

        planned = ttk.LabelFrame(parent, text="Planned metadata integrations", padding=16)
        planned.grid(row=1, column=0, sticky="ew", padx=(0, 8), pady=(8, 0))
        for name in ("ISBNdb", "WorldCat", "Goodreads"):
            ttk.Label(planned, text=f"{name} — planned; not integrated.", wraplength=560).pack(anchor="w", pady=2)

        diagnostic = ttk.LabelFrame(parent, text="ISBN Lookup Test", padding=10)
        diagnostic.grid(row=0, column=1, rowspan=2, sticky="nsew")
        ttk.Label(
            diagnostic,
            text="Test one provider's metadata retrieval capability to diagnose missing metadata or provider failures.",
            wraplength=390,
        ).pack(anchor="w", pady=(0, 6))
        self._provider_test_panel = MetadataProviderTestPanel(
            diagnostic, credentials=self._load_api_credentials()
        )
        self._provider_test_panel.pack(fill="both", expand=True)

    def _build_api_management(self, parent):
        self._api_credential_vars = {}
        self._api_credential_status = {}
        self._api_credential_entries = {}
        descriptions = {
            "google_books": ("Google Books", "Google Books API key", "An API key is optional and identifies BookLedger for public metadata lookups."),
            "bigbook": ("Bigbook", "Bigbook API key", "An API key is required to search Bigbook by ISBN and retrieve verified book metadata."),
            "hardcover": ("Hardcover", "Hardcover API token", "A personal API token is required. Keep it private; it grants access to your Hardcover account."),
        }
        saved_credentials = self._load_api_credentials()
        for provider_id, (name, credential_label, description) in descriptions.items():
            section = ttk.LabelFrame(parent, text=name, padding=12)
            section.pack(fill="x", anchor="n", pady=(0, 10))
            section.columnconfigure(0, minsize=140)
            ttk.Label(section, text=description, wraplength=920).grid(row=0, column=0, columnspan=7, sticky="w", pady=(0, 8))
            field_label = ttk.Label(section, text=credential_label)
            field_label.grid(row=1, column=0, sticky="w", padx=(0, 8))
            field_label.bind("<Enter>", lambda event, help_text=description: self._show_hover_tooltip(event, help_text))
            field_label.bind("<Leave>", self._hide_hover_tooltip)
            variable = tk.StringVar(value=saved_credentials.get(provider_id, ""))
            entry = ttk.Entry(section, textvariable=variable, show="•", width=28)
            entry.grid(row=1, column=1, sticky="w", padx=(0, 6))
            entry.bind("<Enter>", lambda event, help_text=description: self._show_hover_tooltip(event, help_text))
            entry.bind("<Leave>", self._hide_hover_tooltip)
            show_var = tk.BooleanVar(value=False)
            show_button = ttk.Button(section, text="Show")

            def toggle_visibility(entry=entry, variable=show_var, button=show_button):
                visible = not variable.get()
                variable.set(visible)
                entry.configure(show="" if visible else "•")
                button.configure(text="Hide" if visible else "Show")

            show_button.configure(command=toggle_visibility)
            show_button.configure(width=8)
            show_button.grid(row=1, column=2, padx=3, sticky="w")
            save_command = self._save_google_books_key if provider_id == "google_books" else lambda key=provider_id: self._save_provider_credential(key)
            remove_command = self._remove_google_books_key if provider_id == "google_books" else lambda key=provider_id: self._remove_provider_credential(key)
            test_command = self._test_google_books_lookup if provider_id == "google_books" else lambda key=provider_id: self._test_provider_credential(key)
            ttk.Button(section, text="Test Lookup", width=12, command=test_command).grid(row=1, column=3, padx=3, sticky="w")
            ttk.Button(section, text="Save", width=8, command=save_command).grid(row=1, column=4, padx=3, sticky="w")
            ttk.Button(section, text="Remove", width=9, command=remove_command).grid(row=1, column=5, padx=3, sticky="w")
            ttk.Button(section, text="?", width=3, command=lambda item=name: self._show_api_help(item)).grid(row=1, column=6, padx=(3, 0), sticky="w")
            status = tk.StringVar(value="Saved credentials are masked." if saved_credentials.get(provider_id) else "No saved credential.")
            status_label = ttk.Label(section, textvariable=status, wraplength=920)
            status_label.grid(row=2, column=0, columnspan=7, sticky="w", pady=(8, 0))
            self._bind_status_color(status, status_label)
            self._api_credential_vars[provider_id] = variable
            self._api_credential_status[provider_id] = status
            self._api_credential_entries[provider_id] = entry
            if provider_id == "google_books":
                self.google_books_key_var = variable
                self.google_books_key_entry = entry
                self.google_books_api_status = status
                self.google_books_api_status_label = status_label
                self.google_books_show_var = show_var

        configuration_messages = list(self._configuration_warnings)
        if self.provider_settings_store.warning and self.provider_settings_store.warning not in configuration_messages:
            configuration_messages.insert(0, self.provider_settings_store.warning)
        config_warning = " ".join(configuration_messages)
        if config_warning:
            self.google_books_api_status.set(config_warning)

    def _show_api_help(self, provider):
        help_content = {
            "Google Books": (
                "BookLedger uses the Google Books API to retrieve public book metadata. An API key identifies the application and is optional for the current integration. Google explains API keys and credentials here:",
                "https://developers.google.com/books/docs/v1/using",
            ),
            "Bigbook": (
                "BookLedger uses Bigbook to retrieve ISBN-matched book metadata. A Bigbook API key is required and is stored locally in config.json.",
                "https://bigbookapi.com/docs/",
            ),
            "Hardcover": (
                "BookLedger uses Hardcover to retrieve edition-specific book metadata. A personal API token is required. Keep it private; the API is in beta and its schema may change.",
                "https://docs.hardcover.app/api/getting-started/",
            ),
        }
        content = help_content.get(provider)
        if content is None:
            messagebox.showinfo(f"{provider} Help", f"{provider} is planned but is not integrated.", parent=self)
            return None
        message, url = content
        dialog = tk.Toplevel(self)
        apply_application_icon(dialog)
        dialog.title(f"{provider} API Help")
        dialog.transient(self)
        dialog.resizable(False, False)
        body = ttk.Frame(dialog, padding=(16, 14, 16, 12))
        body.pack(fill="both", expand=True)
        icon = ttk.Label(body, text="ℹ", foreground="#168bd2", font=("Segoe UI", 28, "bold"), width=2, anchor="center")
        icon.grid(row=0, column=0, rowspan=2, sticky="n", padx=(0, 10))
        ttk.Label(body, text=message, wraplength=340, justify="left").grid(row=0, column=1, sticky="w")
        link = ttk.Label(body, text=url, foreground="#0563c1", cursor="hand2", takefocus=True, font=("Segoe UI", 9, "underline"))
        link.grid(row=1, column=1, sticky="w", pady=(9, 0))

        def open_documentation(_event=None):
            try:
                opened = webbrowser.open(url, new=2)
            except (OSError, webbrowser.Error):
                opened = False
            if not opened:
                messagebox.showerror("Could not open documentation", "The documentation page could not be opened.", parent=dialog)

        link.bind("<Button-1>", open_documentation)
        link.bind("<Return>", open_documentation)
        footer = ttk.Frame(dialog, padding=(12, 8))
        footer.pack(fill="x", side="bottom")
        ttk.Separator(dialog, orient="horizontal").pack(fill="x", side="bottom")
        close_button = ttk.Button(footer, text="OK", command=dialog.destroy)
        close_button.pack(side="right", ipadx=14)
        dialog.bind("<Return>", lambda _event: dialog.destroy())
        dialog.bind("<Escape>", lambda _event: dialog.destroy())
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        dialog.update_idletasks()
        width = max(410, min(500, body.winfo_reqwidth() + 34))
        height = max(170, body.winfo_reqheight() + footer.winfo_reqheight() + 34)
        x = self.winfo_rootx() + max((self.winfo_width() - width) // 2, 0)
        y = self.winfo_rooty() + max((self.winfo_height() - height) // 2, 0)
        dialog.geometry(f"{width}x{height}+{x}+{y}")
        dialog.grab_set()
        close_button.focus_set()
        return dialog

    def _build_storage_settings(self, parent):
        parent.columnconfigure((0, 1, 2), weight=1, uniform="storage")
        backups = ttk.LabelFrame(parent, text="Backup and verification", padding=12)
        backups.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        backup_actions = (
            ("Back Up Now", self.create_backup, "Create a verified snapshot of the current library."),
            ("Restore Backup…", self.restore_backup, "Replace the current library with a verified backup."),
            ("Export to CSV…", self.export_inventory_csv, "Export the inventory table to a CSV file."),
            ("Verify Database", self.verify_database, "Check database integrity and managed files."),
        )
        for text, command, help_text in backup_actions:
            button = ttk.Button(backups, text=text, command=command)
            button.pack(fill="x", pady=3)
            self._add_hover_tooltip(button, help_text)

        recovery = ttk.LabelFrame(parent, text="Copy and storage recovery", padding=12)
        recovery.grid(row=0, column=1, sticky="nsew", padx=6)
        count = self.lifecycle.trash_count()
        recovery_actions = (
            ("Undo Delete", self.restore_latest, "Restore the most recently deleted copy.", "normal" if count else "disabled"),
            ("Retry Recovery", self.retry_storage_recovery, "Retry interrupted photo and storage operations.", "normal"),
            ("Clear Trash…", self.clear_trash, "Permanently remove copies currently in Trash.", "normal" if count else "disabled"),
            ("Purge Data…", self.purge_data, "Reset the library and settings. Backups are retained.", "normal"),
        )
        for text, command, help_text, state in recovery_actions:
            button = ttk.Button(recovery, text=text, state=state, command=command)
            button.pack(fill="x", pady=3)
            self._add_hover_tooltip(button, help_text)

        logging_panel = ttk.LabelFrame(parent, text="Diagnostic log", padding=12)
        logging_panel.grid(row=0, column=2, sticky="nsew", padx=(6, 0))
        self.logging_var = tk.BooleanVar(value=self._logging_enabled)
        self.view_log_button = ttk.Button(logging_panel, text="View Log", command=self.view_log, state="normal" if self._logging_enabled else "disabled")
        self.view_log_button.pack(fill="x", pady=3)
        self._add_hover_tooltip(self.view_log_button, "Open the optional technical diagnostic log.")
        self.clear_log_button = ttk.Button(logging_panel, text="Clear Log…", command=self.clear_log, state="normal" if self._logging_enabled else "disabled")
        self.clear_log_button.pack(fill="x", pady=3)
        self._add_hover_tooltip(self.clear_log_button, "Clear the optional technical diagnostic log.")
        logging_toggle = ttk.Checkbutton(logging_panel, text="Enable Logging", variable=self.logging_var, command=self._toggle_logging)
        logging_toggle.pack(anchor="w", pady=(8, 3))
        self._add_hover_tooltip(logging_toggle, "Save technical diagnostics to a rotating local log file.")
        self.logging_status_var = tk.StringVar(value=self._logging_warning or ("Logging is enabled." if self._logging_enabled else "Logging is off."))
        self.logging_status_label = ttk.Label(logging_panel, textvariable=self.logging_status_var, wraplength=220)
        self.logging_status_label.pack(anchor="w", pady=(4, 0))
        self._bind_status_color(self.logging_status_var, self.logging_status_label)

    def _build_poster_setup(self, parent):
        self.poster_designer = PosterDesigner(
            parent, service=self.posters, config_store=self.config_store,
            catalog=self.catalog, paths=self.paths, on_open_folder=self._open_poster_folder,
            mousewheel_router=self._mousewheel_router,
            on_activity=lambda event, identifier: self._log_event(
                event, **({"template_id": identifier} if event.startswith("poster_template_") else {"copy_id": identifier})
            ),
        )
        self.poster_designer.pack(fill="both", expand=True)

    def _build_preferences(self, parent):
        self._value_list_editors = {}
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
        themes = ttk.LabelFrame(parent, text="Customize", padding=12)
        themes.grid(row=1, column=1, sticky="nsew", padx=(6, 0), pady=(6, 0))
        ttk.Label(themes, text="Choose from themes available in this installation.", foreground="#64748b").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        ttk.Label(themes, text="Theme:").grid(row=1, column=0, sticky="w", padx=(0, 6))
        self.theme_var = tk.StringVar(value=self._theme_label_by_name.get(self._active_theme, self._active_theme))
        self.theme_selector = ttk.Combobox(
            themes,
            values=tuple(label for label, _name in self._theme_options),
            state="readonly",
            textvariable=self.theme_var,
            width=22,
        )
        self.theme_selector.grid(row=1, column=1, sticky="ew")
        ttk.Button(themes, text="Apply", command=self._apply_theme_selection).grid(row=2, column=1, pady=(10, 0), sticky="w")
        themes.columnconfigure((0, 1), weight=1, uniform="customize_columns")
        action_button = {"width": 16, "padding": (8, 6)}
        ttk.Button(themes, text="Change Logo", command=self._change_shop_logo, **action_button).grid(row=3, column=0, sticky="ew", padx=(0, 4), pady=(12, 4))
        ttk.Button(themes, text="Clear Logo", command=self._clear_shop_logo, **action_button).grid(row=3, column=1, sticky="ew", padx=(4, 0), pady=(12, 4))
        ttk.Button(themes, text="Add Logo Link", command=self._save_shop_url, **action_button).grid(row=4, column=0, sticky="ew", padx=(0, 4), pady=4)
        ttk.Button(themes, text="Clear Logo Link", command=self._clear_shop_url, **action_button).grid(row=4, column=1, sticky="ew", padx=(4, 0), pady=4)
        self.shop_url_var = tk.StringVar(value=str(self.config_store.get(("preferences", "shop_url"), "") or ""))
        self.shop_url_entry = ttk.Entry(themes, textvariable=self.shop_url_var)
        self.shop_url_entry.grid(row=5, column=0, columnspan=2, sticky="ew")
        self.shop_url_entry.bind("<Return>", lambda _event: self._save_shop_url())

        ttk.Label(themes, text="Currency:").grid(row=6, column=0, sticky="w", padx=(0, 6), pady=(12, 0))
        currency = getattr(self, "currency", "PHP")
        self.currency_var = tk.StringVar(value=_currency_option(currency))
        currency_choices = tuple(_currency_option(code) for code in SUPPORTED_CURRENCIES)
        self.currency_selector = ttk.Combobox(themes, values=currency_choices, state="readonly", textvariable=self.currency_var, width=16)
        self.currency_selector.grid(row=6, column=1, sticky="ew", pady=(12, 0))
        ttk.Button(themes, text="Apply Currency", command=lambda: self._apply_currency_selection()).grid(row=7, column=0, sticky="ew", padx=(0, 4), pady=(6, 0))
        ttk.Button(themes, text="Convert Currency…", command=lambda: self._open_currency_conversion()).grid(row=7, column=1, sticky="ew", padx=(4, 0), pady=(6, 0))

    def _apply_currency_selection(self):
        destination = _currency_code(self.currency_var.get())
        if destination == self.currency:
            return
        counts = self.currency_service.monetary_counts()
        if not any(counts.values()):
            self._commit_currency_change(destination, convert=False)
            return
        choice = messagebox.askyesnocancel(
            "Change Currency",
            "Convert existing asking prices, sale history, and SRPs?\n\n"
            "Yes converts the stored values using an exchange rate.\n"
            "No keeps the numbers and reinterprets them in the new currency.\n"
            "Cancel keeps the current currency and all values.",
            parent=self,
        )
        if choice is None:
            self.currency_var.set(_currency_option(self.currency))
        elif choice:
            self._preview_and_convert(self.currency, destination)
        else:
            self._commit_currency_change(destination, convert=False)

    def _open_currency_conversion(self):
        dialog = tk.Toplevel(self)
        dialog.title("Convert Currency")
        dialog.transient(self)
        dialog.grab_set()
        ttk.Label(dialog, text="Convert all retained monetary records.", padding=(12, 12, 12, 4)).grid(row=0, column=0, columnspan=2, sticky="w")
        from_var = tk.StringVar(value=_currency_option(self.currency))
        to_var = tk.StringVar(value=_currency_option(self.currency))
        for row, label, variable in ((1, "From:", from_var), (2, "To:", to_var)):
            ttk.Label(dialog, text=label).grid(row=row, column=0, sticky="w", padx=12, pady=4)
            ttk.Combobox(dialog, values=tuple(_currency_option(code) for code in SUPPORTED_CURRENCIES), state="readonly", textvariable=variable, width=16).grid(row=row, column=1, sticky="ew", padx=(4, 12), pady=4)
        status = tk.StringVar(value="")
        ttk.Label(dialog, textvariable=status, wraplength=420, justify="left").grid(row=3, column=0, columnspan=2, sticky="ew", padx=12, pady=8)

        def preview():
            source, destination = _currency_code(from_var.get()), _currency_code(to_var.get())
            if source == destination:
                status.set("The currencies are identical; no conversion or API request is needed.")
                return
            if source != self.currency and not messagebox.askyesno(
                "Source Currency Differs",
                f"The library is currently labeled {self.currency}, but the stored values will be treated as {source}. Continue?",
                parent=dialog,
            ):
                return
            self._preview_and_convert(source, destination, parent=dialog, close_dialog=dialog)

        ttk.Button(dialog, text="Preview and Convert…", command=preview).grid(row=4, column=0, sticky="ew", padx=12, pady=(4, 12))
        ttk.Button(dialog, text="Cancel", command=dialog.destroy).grid(row=4, column=1, sticky="ew", padx=12, pady=(4, 12))
        dialog.columnconfigure(1, weight=1)

    def _preview_and_convert(self, source, destination, *, parent=None, close_dialog=None):
        parent = parent or self
        try:
            counts = self.currency_service.monetary_counts(source=source)
            if not any(counts.values()):
                if messagebox.askyesno("Change Currency", f"There are no monetary records to convert. Set the library currency to {destination}?", parent=parent):
                    self._commit_currency_change(destination, convert=False)
                    if close_dialog is not None:
                        close_dialog.destroy()
                    return True
                return False
            rate_info = self.currency_service.exchange_rates.get_rate(source, destination)
            examples = []
            with self.db.connect() as conn:
                for table, column, label in (("copies", "price_minor", "Asking price"), ("sales", "price_minor", "Sale"), ("book_records", "srp_minor", "SRP")):
                    predicate = " WHERE srp_minor IS NOT NULL" if table == "book_records" else ""
                    row = conn.execute(f"SELECT {column} FROM {table}{predicate} ORDER BY id LIMIT 1").fetchone()
                    if row:
                        from bookledger.services.currency import convert_minor
                        converted = convert_minor(row[0], rate_info["rate"])
                        examples.append(f"{label}: {format_money(row[0], source)} → {format_money(converted, destination)}")
            summary = (
                f"Source: {source}  ·  Destination: {destination}\n"
                f"Rate: 1 {source} = {rate_info['rate']} {destination}\n"
                f"Observation date: {rate_info['rate_date']}  ·  Source: {rate_info['source']}\n"
                f"Records: {counts['asking_prices']} asking prices, {counts['sales']} sales (including voided), {counts['srps']} SRPs\n"
                + ("\n".join(examples) if examples else "No monetary records are affected.")
                + "\n\nAmounts are rounded to two decimal places. A recovery backup will be created before conversion."
            )
            if messagebox.askyesno("Confirm Currency Conversion", summary, parent=parent):
                self._commit_currency_change(destination, convert=True, rate_info=rate_info, source=source)
                if close_dialog is not None:
                    close_dialog.destroy()
                return True
        except Exception as exc:
            messagebox.showerror("Currency Conversion Failed", str(exc), parent=parent)
        return False

    def _commit_currency_change(self, destination, *, convert, rate_info=None, source=None):
        try:
            self.currency_service.set_currency(destination, convert=convert, rate_info=rate_info, source=source)
            self.currency = self.currency_service.current()
            self.currency_var.set(_currency_option(self.currency))
            self.show_page(self.current_page)
            self.status_var.set(f"Currency set to {self.currency}.")
        except Exception as exc:
            self.currency = self.currency_service.current()
            self.currency_var.set(_currency_option(self.currency))
            messagebox.showerror("Currency Change Failed", str(exc), parent=self)
            if self.currency != destination:
                return
            self.show_page(self.current_page)
            self.status_var.set(f"Currency is {self.currency}; settings reconciliation will be retried at startup.")

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
        wheel_router = getattr(self, "_mousewheel_router", None)
        if wheel_router is not None:
            wheel_router.register(canvas, list_frame)
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
            editor_rows = {}
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
                handle = ttk.Label(item, text="⠿", cursor="fleur", foreground="#64748b", padding=(5, 0))
                handle.grid(row=0, column=3, padx=(2, 4))
                editor_rows[value] = item
                for widget in (name_label, handle):
                    widget.bind("<ButtonPress-1>", lambda event, list_kind=kind, name=value: self._value_drag_start(event, list_kind, name))
                    widget.bind("<B1-Motion>", self._value_drag_motion)
                    widget.bind("<ButtonRelease-1>", self._value_drag_end)
                if count:
                    explanation = f"Cannot delete this {kind} because one or more books are assigned to it. Rename it to migrate the assignments, or update those books first."
                    delete_button._tooltip_bounds = panel
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
                            self._log_event(f"{kind}_rename_failed")
                            status_var.set(str(exc))
                            return
                        if replacement != old_value:
                            self._log_event(f"{kind}_renamed")
                        status_var.set(f"{title} saved.")
                        refresh()

                    ttk.Button(row_widget, text="Save", width=7, command=save_rename).grid(row=0, column=1, padx=2)
                    ttk.Button(row_widget, text="Cancel", width=7, command=refresh).grid(row=0, column=2, padx=2)
                    edit.focus_set()
                    edit.selection_range(0, "end")

                rename_button.configure(command=begin_rename)
            canvas.yview_moveto(0)
            self._value_list_editors[kind] = {
                "rows": editor_rows, "values": list(editor_rows), "list": list_values,
                "canvas": canvas, "status": status_var, "title": title, "refresh": refresh,
            }

        def add():
            try:
                value = add_value(add_entry.get())
            except (ValueError, OSError, sqlite3.Error) as exc:
                self._log_event(f"{kind}_add_failed")
                status_var.set(str(exc))
                return
            self._log_event(f"{kind}_added")
            add_entry.delete(0, "end")
            status_var.set(f"{title} added.")
            refresh()
            canvas.yview_moveto(1.0)

        def delete(value):
            try:
                delete_value(value)
            except (ValueError, OSError, sqlite3.Error) as exc:
                self._log_event(f"{kind}_delete_failed")
                status_var.set(str(exc))
                refresh()
                return
            self._log_event(f"{kind}_deleted")
            status_var.set(f"{title} deleted.")
            refresh()

        ttk.Button(add_row, text="Add New", command=add).pack(side="left", padx=(6, 0))
        refresh()

    def _value_drag_start(self, _event, kind, value):
        self._value_drag = (kind, value)

    def _value_drag_motion(self, event):
        drag = getattr(self, "_value_drag", None)
        if not drag:
            return
        kind, moving = drag
        editor = self._value_list_editors.get(kind)
        if not editor or moving not in editor["values"]:
            return
        values = list(editor["values"])
        target_y = event.y_root
        for value in values:
            if value == moving:
                continue
            row = editor["rows"].get(value)
            if row is not None and target_y < row.winfo_rooty() + row.winfo_height() / 2:
                values.remove(moving)
                values.insert(values.index(value), moving)
                break
        else:
            values.remove(moving)
            values.append(moving)
        self._reorder_value_rows(kind, values)

    def _reorder_value_rows(self, kind, values):
        editor = self._value_list_editors.get(kind)
        if not editor:
            return
        editor["values"] = list(values)
        for index, value in enumerate(values):
            editor["rows"][value].grid_configure(row=index)

    def _value_drag_end(self, _event=None):
        drag = getattr(self, "_value_drag", None)
        self._value_drag = None
        if not drag:
            return
        kind, _moving = drag
        editor = self._value_list_editors.get(kind)
        if not editor:
            return
        key = {"genre": "genres", "format": "formats", "location": "locations"}[kind]
        previous = editor.get("list", lambda: editor["values"])()
        try:
            self.config_store.set(("preferences", key), editor["values"])
            if previous != editor["values"]:
                self._log_event(f"{kind}_order_changed")
            editor["status"].set(f"{editor['title']} order saved.")
        except (OSError, ValueError, sqlite3.Error) as exc:
            self._log_event(f"{kind}_order_change_failed")
            editor["status"].set(f"Could not save {editor['title']} order: {exc}")
            editor["refresh"]()

    def _show_hover_tooltip(self, event, message):
        self._hide_hover_tooltip()
        try:
            # Keep the tooltip in its own native window: it is never a child
            # managed by the hovered panel's grid/pack geometry.
            tip = tk.Toplevel(self.winfo_toplevel())
            tip.wm_overrideredirect(True)
            tip.wm_attributes("-topmost", True)
            wraplength = 340
            x, y = event.x_root + 12, event.y_root + 12
            bounds = getattr(getattr(event, "widget", None), "_tooltip_bounds", None)
            if bounds is not None and bounds.winfo_width() > 1:
                left = bounds.winfo_rootx()
                right = left + bounds.winfo_width()
                right_width = right - x - 20
                left_width = event.x_root - left - 20
                if right_width >= 180:
                    wraplength = min(wraplength, right_width)
                elif left_width >= 180:
                    wraplength = min(wraplength, left_width)
                    x = event.x_root - wraplength - 20
                else:
                    wraplength = max(160, min(240, bounds.winfo_width() - 16))
                    x = left + 8
            ttk.Label(tip, text=message, wraplength=wraplength, padding=8, relief="solid").pack()
            width, height = tip.winfo_reqwidth(), tip.winfo_reqheight()
            screen_width, screen_height = tip.winfo_screenwidth(), tip.winfo_screenheight()
            if x + width > screen_width:
                x = event.x_root - width - 12
            if y + height > screen_height:
                y = event.y_root - height - 12
            x = max(0, min(x, max(0, screen_width - width)))
            y = max(0, min(y, max(0, screen_height - height)))
            tip.wm_geometry(f"+{x}+{y}")
            self._hover_tooltip = tip
        except tk.TclError:
            self._hover_tooltip = None

    def _add_hover_tooltip(self, widget, message):
        widget.bind("<Enter>", lambda event, help_text=message: self._show_hover_tooltip(event, help_text), add="+")
        widget.bind("<Leave>", self._hide_hover_tooltip, add="+")

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
        previous_order = list(self.provider_settings.order)
        previous_enabled = dict(self.provider_settings.enabled)
        self.provider_settings.order = order
        self.provider_settings.enabled = {
            provider_id: bool(variable.get()) for provider_id, variable in self._provider_variables.items()
        }
        try:
            saved_path = self.provider_settings_store.save(self.provider_settings)
        except OSError as exc:
            self._log_event("metadata_provider_settings_save_failed")
            self._provider_config_status.set(f"Could not save provider settings: {exc}")
            return
        self.metadata_lookup = MetadataLookupService(
            build_providers(self.provider_settings, credentials=self._load_api_credentials())
        )
        if previous_order != order:
            self._log_event("metadata_provider_order_changed")
        for provider_id, enabled in self.provider_settings.enabled.items():
            if previous_enabled.get(provider_id) != enabled:
                self._log_event(
                    "metadata_provider_enabled" if enabled else "metadata_provider_disabled",
                    provider_id=provider_id,
                )
        self._provider_config_status.set(f"Provider settings saved to {saved_path}")

    def _restore_provider_defaults(self):
        self.provider_settings = ProviderSettings.defaults()
        for provider_id, variable in self._provider_variables.items():
            variable.set(self.provider_settings.enabled.get(provider_id, True))
        self._reorder_provider_rows(list(self.provider_settings.order))
        self._save_provider_settings()

    def _load_google_books_key(self):
        return BookLedgerApp._load_api_credentials(self).get("google_books", "")

    def _load_api_credentials(self):
        credentials = {}
        try:
            for provider_id in ("google_books", "bigbook", "hardcover"):
                value = self.config_store.get(("api_keys", provider_id), "")
                credentials[provider_id] = value if isinstance(value, str) else ""
        except (OSError, ValueError, AttributeError):
            return {"google_books": "", "bigbook": "", "hardcover": ""}
        return credentials

    def _apply_api_credentials(self, credentials):
        values = dict(credentials)
        self.metadata_lookup = MetadataLookupService(
            build_providers(self.provider_settings, credentials=values)
        )
        panel = getattr(self, "_provider_test_panel", None)
        if panel is not None:
            panel._api_credentials = values

    def _apply_google_books_key(self, api_key):
        credentials = self._load_api_credentials()
        credentials["google_books"] = api_key
        self._apply_api_credentials(credentials)

    def _save_provider_credential(self, provider_id):
        try:
            existed = self.config_store.get(("api_keys", provider_id), None) is not None
            credential = self._api_credential_vars[provider_id].get().strip()
            self.config_store.set(("api_keys", provider_id), credential)
            credentials = self._load_api_credentials()
            credentials[provider_id] = credential
            self._apply_api_credentials(credentials)
        except (OSError, ValueError, KeyError) as exc:
            self._log_event("api_credential_save_failed", provider_id=provider_id)
            self._api_credential_status[provider_id].set(f"Could not save {provider_id} settings: {exc}")
            return False
        self._api_credential_status[provider_id].set("Credential saved locally and masked.")
        self._log_event(
            "api_credential_replaced" if existed else "api_credential_saved",
            provider_id=provider_id,
        )
        return True

    def _remove_provider_credential(self, provider_id):
        provider_names = {"bigbook": "Bigbook", "hardcover": "Hardcover"}
        name = provider_names[provider_id]
        if not messagebox.askyesno(
            f"Remove {name} credential?",
            f"Remove the saved {name} credential from BookLedger? Other API credentials will be kept.",
            parent=self,
        ):
            return False
        try:
            existed = self.config_store.get(("api_keys", provider_id), None) is not None
            if existed:
                self.config_store.remove(("api_keys", provider_id))
            self._api_credential_vars[provider_id].set("")
            credentials = self._load_api_credentials()
            credentials[provider_id] = ""
            self._apply_api_credentials(credentials)
        except (OSError, ValueError, KeyError) as exc:
            self._log_event("api_credential_remove_failed", provider_id=provider_id)
            self._api_credential_status[provider_id].set(f"Could not remove {name} credential: {exc}")
            return False
        self._api_credential_status[provider_id].set(
            f"Saved {name} credential removed." if existed else f"No saved {name} credential was present."
        )
        if existed:
            self._log_event("api_credential_removed", provider_id=provider_id)
        return True

    def _test_provider_credential(self, provider_id):
        descriptor = next((item for item in PROVIDER_REGISTRY if item.id == provider_id), None)
        if descriptor is None:
            return False
        credential = self._api_credential_vars[provider_id].get().strip()
        self._api_credential_status[provider_id].set("Testing a sample ISBN metadata lookup…")

        def worker():
            succeeded = False
            try:
                result = descriptor.factory(credential).lookup("9780306406157")
                outcomes = {
                    "authentication": "Authentication failed or credential is missing.",
                    "authorization": "Provider denied access to the request.",
                    "quota": "Bigbook request quota is exhausted.",
                    "rate_limit": "Provider rate limit reached; try again later.",
                    "timeout": "Provider lookup timed out.",
                    "network": "Could not connect to the provider.",
                    "provider": "Provider returned an HTTP error.",
                    "unexpected": "Provider returned an invalid response.",
                }
                if result.status == "Lookup failed":
                    message = outcomes.get(result.failure_kind, "Sample metadata lookup failed.")
                elif result.failure_kind == "unverified":
                    message = "Search returned records, but none matched the sample ISBN."
                elif result.status == "No data" and result.record_found is False:
                    message = "No sample ISBN record was found."
                elif result.values:
                    message = "Sample metadata lookup succeeded; some fields may be unavailable."
                else:
                    message = "A matching record was found, but no supported metadata was available."
                succeeded = result.status != "Lookup failed"
            except Exception:
                message = "Sample metadata lookup failed."

            def complete():
                try:
                    if self.winfo_exists():
                        self._api_credential_status[provider_id].set(message)
                        log_event = getattr(self, "_log_event", None)
                        if log_event:
                            log_event(
                                "api_credential_test_succeeded" if succeeded else "api_credential_test_failed",
                                provider_id=provider_id,
                            )
                except tk.TclError:
                    pass

            try:
                self.after(0, complete)
            except tk.TclError:
                pass

        try:
            threading.Thread(target=worker, name=f"BookLedger{descriptor.name}CredentialTest", daemon=True).start()
        except RuntimeError:
            self._log_event("api_credential_test_failed", provider_id=provider_id)
            self._api_credential_status[provider_id].set("Could not start the sample metadata lookup.")
            return False
        return True

    def _save_google_books_key(self):
        try:
            existed = self.config_store.get(("api_keys", "google_books"), None) is not None
            api_key = self.google_books_key_var.get().strip()
            self.config_store.set(("api_keys", "google_books"), api_key)
            self._apply_google_books_key(api_key)
        except (OSError, ValueError) as exc:
            self._log_event("api_credential_save_failed", provider_id="google_books")
            self.google_books_api_status.set(f"Could not save Google Books settings: {exc}")
            return False
        self.google_books_api_status.set("Google Books API settings saved.")
        self._log_event(
            "api_credential_replaced" if existed else "api_credential_saved",
            provider_id="google_books",
        )
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
            self._log_event("api_credential_remove_failed", provider_id="google_books")
            self.google_books_api_status.set(f"Could not remove Google Books API key: {exc}")
            return
        self.google_books_api_status.set(
            "Saved Google Books API key removed." if existed else "No saved Google Books API key was present."
        )
        if existed:
            self._log_event("api_credential_removed", provider_id="google_books")

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
                        self._log_event(
                            "api_credential_test_succeeded" if succeeded else "api_credential_test_failed",
                            provider_id="google_books",
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
            self._log_event("api_credential_test_failed", provider_id="google_books")
            self.google_books_api_status.set(f"Could not start Google Books lookup: {type(exc).__name__}")

    def open_isbn_lookup_test(self):
        return MetadataProviderTestDialog(
            self, google_books_api_key=self._load_google_books_key()
        )

    def _catalog_action_button(self, parent, **kwargs):
        button = ttk.Button(parent, **kwargs)
        if self._incoming_reception_active:
            self._catalog_action_states[button] = kwargs.get("state", "normal")
            button.configure(state="disabled")
        self._catalog_action_buttons.append(button)
        return button

    def _queue_reception_state(self, active):
        try:
            self.after(0, lambda: self._set_reception_state(active))
        except (tk.TclError, RuntimeError):
            pass

    def _queue_mobile_indicator(self):
        self._mobile_indicator_refresh_pending.set()

    def _poll_mobile_indicator(self):
        if not self._mobile_indicator_polling:
            return
        service = self.mobile_connection_service
        connected = service.connected
        if (
            self._mobile_indicator_refresh_pending.is_set()
            or connected != self._mobile_indicator_last_connected
        ):
            self._mobile_indicator_refresh_pending.clear()
            self._update_mobile_connection_indicator()
        try:
            self.after(1000, self._poll_mobile_indicator)
        except (tk.TclError, RuntimeError):
            self._mobile_indicator_polling = False

    def _update_mobile_connection_indicator(self):
        label = getattr(self, "mobile_connection_status_label", None)
        variable = getattr(self, "mobile_connection_status_var", None)
        service = getattr(self, "mobile_connection_service", None)
        if label is None or variable is None or service is None:
            return
        if getattr(self, "_incoming_reception_active", False):
            text, color = "● Receiving", WARNING_COLOR
        elif service.paired and service.connected:
            text, color = "● Paired - Connected", SUCCESS_COLOR
        elif service.paired:
            text = "● Paired - Not Connected"
            color = ERROR_COLOR if service.status == "error" else WARNING_COLOR
        else:
            text, color = "● Not Paired", NEUTRAL_COLOR
        if service.status == "error":
            if not getattr(self, "_mobile_service_error_logged", False):
                log_event = getattr(self, "_log_event", None)
                if log_event:
                    log_event("mobile_service_failed")
                self._mobile_service_error_logged = True
        if service.status != "error":
            self._mobile_service_error_logged = False
        variable.set(text)
        label.configure(foreground=color)
        self._mobile_indicator_last_connected = service.connected

    def _record_mobile_activity(self, event):
        try:
            self.mobile_activity_store.record(event)
        except (OSError, sqlite3.Error, ValueError):
            self._log_event("mobile_activity_record_failed")
            return
        try:
            self.after(0, self._refresh_mobile_activity)
        except (tk.TclError, RuntimeError):
            pass

    def _refresh_mobile_activity(self):
        panel = getattr(self, "_mobile_app_setup_panel", None)
        try:
            if panel is not None and panel.winfo_exists():
                panel.refresh_activity()
        except tk.TclError:
            pass

    def _set_reception_state(self, active):
        self._incoming_reception_active = bool(active)
        for button in tuple(self._catalog_action_buttons):
            try:
                if button.winfo_exists():
                    if active:
                        self._catalog_action_states[button] = button.cget("state")
                        button.configure(state="disabled")
                    else:
                        button.configure(state=self._catalog_action_states.pop(button, "normal"))
                else:
                    self._catalog_action_states.pop(button, None)
            except tk.TclError:
                self._catalog_action_states.pop(button, None)
        if active and hasattr(self, "status_var"):
            self.status_var.set("Receiving books from the mobile companion…")
        self._update_mobile_connection_indicator()

    def _queue_incoming_batch(self, batch_id):
        try:
            self.after(0, lambda: self._start_incoming_cataloging(batch_id))
        except tk.TclError:
            pass

    def _resume_mobile_incoming(self):
        batches = self.mobile_incoming_store.ready_batches()
        if batches:
            self._start_incoming_cataloging(batches[0])

    def _start_incoming_cataloging(self, batch_id):
        if self._incoming_catalog_batch is not None:
            return
        self._incoming_catalog_batch = batch_id
        self._open_next_incoming_capture(batch_id)

    def _open_next_incoming_capture(self, batch_id):
        pending = self.mobile_incoming_store.pending_captures(batch_id)
        if not pending:
            if self.mobile_incoming_store.has_unresolved_catalog_save(batch_id):
                messagebox.showerror(
                    "Incoming Photo Recovery Needed",
                    "A received book was saved, but its desktop photo operation needs recovery. Use Settings → Storage and Backup → Retry Recovery, then restart BookLedger to resume this batch.",
                    parent=self,
                )
                self._incoming_catalog_batch = None
                return
            self.mobile_incoming_store.finish_batch_if_empty(batch_id)
            self._incoming_catalog_batch = None
            messagebox.showinfo(
                "Incoming Batch Complete",
                "All incoming books in this batch have been processed.",
                parent=self,
            )
            remaining = self.mobile_incoming_store.ready_batches()
            if remaining:
                self.after(0, lambda: self._start_incoming_cataloging(remaining[0]))
            return
        capture = pending[0]
        if not capture["photo_path"].is_file():
            messagebox.showerror(
                "Incoming Capture Needs Recovery",
                "A staged photograph is missing. The capture was retained; restore the file before continuing.",
                parent=self,
            )
            self._incoming_catalog_batch = None
            return
        BookForm(
            self,
            service=self.catalog,
            photo_service=self.photos,
            currency=getattr(self, "currency", "PHP"),
            metadata_lookup=self.metadata_lookup,
            mousewheel_router=self._mousewheel_router,
            on_saved=lambda: self._incoming_capture_saved(batch_id, capture["capture_uuid"]),
            on_activity=lambda event, identifier: self._log_event(event, copy_id=identifier),
            initial_isbn=capture["isbn"],
            initial_photo=capture["photo_path"],
            incoming_capture_id=capture["capture_uuid"],
            on_discard_incoming=lambda capture_id: self._discard_incoming_capture(batch_id, capture_id),
            on_cancel=lambda capture_id: self._cancel_incoming_sequence(batch_id, capture_id),
        )

    def _incoming_capture_saved(self, batch_id, capture_id):
        if not self.mobile_incoming_store.finish_cataloged_capture(capture_id):
            messagebox.showerror(
                "Incoming Capture Needs Recovery",
                "The capture was saved, but its staged files could not be finalized. The desktop copy remains saved; retry storage recovery before continuing.",
                parent=self,
            )
            self._incoming_catalog_batch = None
            return
        self.after(50, lambda: self._open_next_incoming_capture(batch_id))

    def _discard_incoming_capture(self, batch_id, capture_id):
        if not self.mobile_incoming_store.discard_capture(capture_id):
            raise RuntimeError("The incoming capture could not be discarded.")
        self.after(50, lambda: self._open_next_incoming_capture(batch_id))
        return True

    def _cancel_incoming_sequence(self, batch_id, capture_id):
        if not self.mobile_incoming_store.discard_capture(capture_id):
            return False
        if self._incoming_catalog_batch == batch_id:
            self._incoming_catalog_batch = None
        return True

    def open_add_form(self):
        if self._incoming_reception_active:
            return
        BookForm(self, service=self.catalog, photo_service=self.photos, metadata_lookup=self.metadata_lookup, currency=getattr(self, "currency", "PHP"),
                 mousewheel_router=self._mousewheel_router,
                 on_saved=lambda: self._after_save("Book saved."), on_activity=lambda event, identifier: self._log_event(event, copy_id=identifier))

    def open_selected_edit(self, copy_id=None):
        if getattr(self, "_incoming_reception_active", False):
            return
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
        BookForm(self, service=self.catalog, photo_service=self.photos, metadata_lookup=getattr(self, "metadata_lookup", None), currency=getattr(self, "currency", "PHP"),
                 mousewheel_router=getattr(self, "_mousewheel_router", None),
                 on_saved=lambda: self._after_save("Book updated."), on_activity=lambda event, identifier: self._log_event(event, copy_id=identifier), existing=row)

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
        fields = [
            ("Title", row.get("title")),
        ]
        if row.get("subtitle"):
            fields.append(("Subtitle", row["subtitle"]))
        fields.extend((
            ("Author", row.get("author")), ("ISBN", row.get("isbn")),
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
        ))
        text_frame = ttk.Frame(frame)
        text_frame.pack(fill="both", expand=True)
        text = tk.Text(text_frame, wrap="word", height=24, relief="flat", background=dialog.cget("background"))
        scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)
        text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        wheel_router = getattr(self, "_mousewheel_router", None)
        if wheel_router is not None:
            wheel_router.register(text, text_frame)
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
            ("srp_minor", f"SRP ({getattr(self, 'currency', 'PHP')})"),
            ("format", "Format"),
            ("condition", "Condition"),
            ("location", "Location"),
            ("price_minor", f"Price ({getattr(self, 'currency', 'PHP')})"),
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

    def export_apk(self):
        source = self.paths.root / "mobile" / "BookLedger-Android.apk"
        if not source.is_file():
            messagebox.showerror(
                "APK unavailable",
                f"BookLedger-Android.apk was not found in {source.parent}.",
                parent=self,
            )
            return False
        destination = filedialog.asksaveasfilename(
            parent=self,
            title="Export BookLedger Android APK",
            initialdir=self.paths.root,
            initialfile=source.name,
            defaultextension=".apk",
            filetypes=[("Android package", "*.apk"), ("All files", "*.*")],
            confirmoverwrite=True,
        )
        if not destination:
            return False
        try:
            shutil.copy2(source, destination)
        except (OSError, shutil.Error) as exc:
            messagebox.showerror(
                "APK export failed",
                f"The Android app could not be exported: {exc}",
                parent=self,
            )
            return False
        self.status_var.set(f"Exported Android app to {Path(destination).name}.")
        messagebox.showinfo(
            "APK export complete",
            f"Exported {source.name}.",
            parent=self,
        )
        return True

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
            path = getattr(self.paths, "log_file", self.paths.root / "log.txt")
            path.parent.mkdir(parents=True, exist_ok=True)
            legacy = self.paths.root / "log.txt"
            if not path.exists() and legacy.is_file():
                shutil.copy2(legacy, path)
            handler = RotatingFileHandler(path, mode="a", maxBytes=1_000_000, backupCount=5, encoding="utf-8", delay=False)
            handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
            logger.addHandler(handler)
            return ""
        except OSError as exc:
            return f"Could not open the activity log for writing: {exc}"

    def _log_event(self, event, **details):
        if getattr(self, "_logging_enabled", False):
            level = logging.WARNING if event.endswith("_failed") else logging.INFO
            try:
                log_activity(self._optional_logger, event, level=level, **details)
            except Exception:
                pass

    def _report_callback_exception(self, exc_type, _exc, _traceback):
        if getattr(self, "_logging_enabled", False):
            try:
                self._optional_logger.error("unexpected_exception type=%s", getattr(exc_type, "__name__", "Exception"))
            except Exception:
                pass

    def _close_application(self):
        self._mobile_indicator_polling = False
        try:
            self.mobile_connection_service.stop()
        except Exception as exc:
            self._log_event(
                "mobile_service_shutdown_failed",
                error_type=type(exc).__name__,
            )
        self._log_event("application_closed")
        for handler in tuple(getattr(self, "_optional_logger", logging.getLogger()).handlers):
            self._optional_logger.removeHandler(handler)
            try:
                handler.close()
            except Exception:
                pass
        self.destroy()

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
            self._log_event("diagnostic_logging_enabled")

    def view_log(self):
        if not self._logging_enabled:
            return
        path = getattr(self.paths, "log_file", self.paths.root / "log.txt")
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
            "Clear diagnostic log?", "Clear the activity log and its rotated history?", parent=self
        ):
            return
        path = getattr(self.paths, "log_file", self.paths.root / "log.txt")
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
            for index in range(1, 6):
                Path(f"{path}.{index}").unlink(missing_ok=True)
            self.logging_status_var.set("Diagnostic log cleared.")
        except OSError as exc:
            messagebox.showerror("Could not clear log", f"The diagnostic log could not be cleared: {exc}", parent=self)

    def create_backup(self):
        try:
            path = self.backups.create_backup()
            self._log_event("backup_created")
            self.status_var.set(f"Backup created: {path.name}")
            messagebox.showinfo("Backup complete", f"Backup saved to:\n{path}", parent=self)
        except Exception as exc:
            self._log_event("backup_creation_failed")
            messagebox.showerror("Backup failed", str(exc), parent=self)

    def restore_backup(self):
        path = filedialog.askopenfilename(parent=self, title="Choose a BookLedger backup", initialdir=self.paths.backups, filetypes=[("BookLedger backup", "*.zip"), ("All files", "*.*")])
        if not path:
            return
        try:
            ok, message = self.backups.verify_archive(path)
        except Exception:
            self._log_event("backup_verification_failed")
            messagebox.showerror("Backup verification failed", "The selected backup could not be verified.", parent=self)
            return
        if not ok:
            self._log_event("backup_verification_failed")
            messagebox.showerror("Backup verification failed", message, parent=self)
            return
        self._log_event("backup_verified")
        if not messagebox.askyesno("Restore backup?", "Restoring replaces the current library, photos, and configuration with the selected snapshot. Changes made after that snapshot will be absent. A recoverable backup of the current library will be saved first. Continue?", parent=self):
            return
        try:
            recovery = self.backups.restore_backup(path)
            if hasattr(self, "currency_service"):
                self.currency = self.currency_service.reconcile()
        except Exception as exc:
            self._log_event("backup_restore_failed")
            messagebox.showerror("Restore failed", f"The backup could not be restored: {exc}", parent=self)
            return
        self._log_event("backup_restored")
        self.status_var.set(f"Restored backup: {Path(path).name}")
        self.refresh_current()
        messagebox.showinfo("Restore complete", f"The snapshot was restored and validated. Recovery point: {recovery.name}\n\nRestart BookLedger to apply restored configuration settings.", parent=self)

    def verify_database(self):
        try:
            report = self.verifier.verify()
        except Exception:
            self._log_event("database_verification_failed")
            raise
        if report.ok:
            self._log_event("database_verified")
            messagebox.showinfo("Database check", report.message, parent=self)
        else:
            self._log_event("database_verification_failed")
            messagebox.showwarning("Database check", report.message, parent=self)

    def restore_latest(self):
        try:
            copy_id = self.lifecycle.restore_latest()
        except Exception as exc:
            self._log_event("physical_copy_restore_failed")
            messagebox.showerror("Restore Failed", str(exc), parent=self)
            return
        if copy_id is not None:
            self._log_event("physical_copy_restored", copy_id=int(copy_id))
            self.status_var.set(f"Restored Copy ID {copy_id}.")
            self.refresh_current()

    def retry_storage_recovery(self):
        try:
            failures = self.lifecycle.retry_pending_operations()
        except Exception:
            self._log_event("storage_recovery_failed")
            raise
        if failures:
            self._log_event("storage_recovery_failed", count=len(failures))
            messagebox.showerror("Recovery Needs Attention", "Some storage operations remain unresolved:\n" + "\n".join(failures), parent=self)
        else:
            self._log_event("storage_recovery_completed")
            messagebox.showinfo("Recovery Complete", "All pending storage operations were completed.", parent=self)
        self.refresh_current()

    def clear_trash(self):
        if not messagebox.askyesno("Permanently Clear Trash?", "This permanently removes trashed copies, their sales history, and unshared photos. This cannot be undone.", parent=self):
            return
        try:
            count = self.lifecycle.clear_trash()
        except Exception as exc:
            self._log_event("trash_clear_failed")
            messagebox.showerror("Clear Trash Incomplete", str(exc), parent=self)
            return
        self._log_event("trash_cleared", count=int(count))
        self.status_var.set(f"Permanently removed {count} trashed copy/copies.")
        self.refresh_current()

    def purge_data(self):
        if not messagebox.askyesno("Reset BookLedger Data?", "This permanently removes the library database, photos, Trash, posters, application settings (including metadata provider settings and API credentials), and the activity log. BookLedger will create a fresh default configuration when the reset completes. Backups in the root backups folder are retained. Create a backup first if you may need this data.", parent=self):
            return
        from tkinter import simpledialog
        typed = simpledialog.askstring("Confirm Purge", "Type PURGE to permanently reset BookLedger data:", parent=self)
        if typed != "PURGE":
            return
        was_logging_enabled = bool(getattr(self, "_logging_enabled", False))
        if was_logging_enabled:
            self._log_event("purge_started")
        # Close the rotating handler before deleting its file, and keep logging
        # disabled until the purge and configuration reset have both finished.
        self._configure_optional_logging(False)
        self._logging_enabled = False
        try:
            config_paths = {
                Path(self.config_store.canonical_path),
                Path(self.config_store.active_path),
            }
            fallback_path = getattr(self.config_store, "fallback_path", None)
            if fallback_path is not None:
                config_paths.add(Path(fallback_path))
            self.lifecycle.purge(config_paths=config_paths, log_paths=(self.paths.log_file,))
            self.paths.prepare()
            self.db = Database(self.paths.database)
            self.mobile_activity_store = MobileActivityStore(self.db)
            # Recreate a default BookLedger configuration with the one-time
            # migration markers set, so a retained legacy profile key cannot
            # silently repopulate settings that Purge just reset.
            self.config_store = AppConfigStore(
                self.paths.provider_config, self.paths.provider_config_fallback()
            )
            self.currency_service = CurrencyService(self.db, ExchangeRateService(self.db), None, self.config_store)
            self.currency = self.currency_service.reconcile()
            if self.currency_service.warning:
                self._configuration_warnings += (self.currency_service.warning,)
            self.config_store.set(("migration_state", "configuration_v1"), True)
            self.config_store.set(("migration_state", "google_books_legacy_checked"), True)
            self.config_store.set(("api_keys", "google_books"), "")
            self.config_store.set(("logging", "enabled"), False)
            self._configuration_warnings = self.config_store.migrate_legacy_settings(
                self.db,
                self.paths.google_books_config,
                self.paths._profile_google_books_config(),
            )
            available_themes = getattr(self, "_available_theme_names", ())
            if available_themes:
                default_theme = default_theme_name(available_themes)
                try:
                    apply_theme_to_style(self.theme_style, default_theme)
                    self._active_theme = default_theme
                    self.config_store.set(("preferences", "theme"), default_theme)
                except Exception:
                    pass
            self.provider_settings_store = ProviderSettingsStore(
                self.paths.provider_config,
                self.paths.provider_config_fallback(),
                config_store=self.config_store,
            )
            self.provider_settings = self.provider_settings_store.load()
            self._logging_enabled = False
            self._logging_warning = ""
            self._configure_optional_logging(False)
            self.catalog = CatalogService(self.db, self.paths.data, config_store=self.config_store)
            self.photos = PhotoService(self.paths.photos, self.paths.trash)
            self.lifecycle = CopyLifecycleService(self.db, self.paths.data)
            self.verifier = VerificationService(self.db, self.paths.data)
            self.backups = BackupService(self.db, self.paths.data, self.paths.backups)
            self.currency_service.backup = self.backups
            self.posters = PosterService(self.db, self.paths, currency=lambda: self.currency)
            self.metadata_lookup = MetadataLookupService(
                build_providers(self.provider_settings)
            )
            self.status_var.set("BookLedger data and settings were reset. Root-level backups were retained.")
            self.show_page("Dashboard")
        except Exception as exc:
            if was_logging_enabled:
                warning = self._configure_optional_logging(True)
                self._logging_enabled = not bool(warning)
            self._log_event("purge_failed")
            messagebox.showerror("Purge Incomplete", f"BookLedger could not complete the purge. The data folder may be partially reset: {exc}", parent=self)

    def _open_path(self, path: Path):
        try:
            if sys.platform == "win32":
                import os
                os.startfile(path)
            else:
                opener = "open" if sys.platform == "darwin" else "xdg-open"
                subprocess.Popen([opener, str(path)])
            return True
        except Exception as exc:
            messagebox.showerror("Could not open folder", str(exc), parent=self)
            return False

    def _open_poster_folder(self):
        try:
            self.paths.posters.mkdir(parents=True, exist_ok=True)
            self.paths.posters.resolve().relative_to(self.paths.data.resolve())
        except (OSError, ValueError) as exc:
            messagebox.showerror("Could not open poster folder", str(exc), parent=self)
            return False
        return self._open_path(self.paths.posters)

    def money(self, minor=None):
        if minor is None:
            return format_money(self, "PHP")
        return format_money(minor, getattr(self, "currency", "PHP"))


def main():
    paths = AppPaths()
    try:
        library_lock = LibraryInstanceLock(paths.root)
    except LibraryAlreadyRunning:
        _show_startup_message(
            "BookLedger is already open for this library. Close the other window before starting another copy.",
            warning=True,
        )
        return 0
    except LibraryLockError as exc:
        _show_startup_message(
            f"BookLedger could not verify exclusive access to this library, so it will not start.\n\n{exc}"
        )
        return 1

    try:
        app = BookLedgerApp(paths)
        app.mainloop()
        return 0
    finally:
        library_lock.close()


def _show_startup_message(message: str, *, warning: bool = False) -> None:
    if sys.platform == "win32":
        try:
            import ctypes

            flags = (0x30 if warning else 0x10) | 0x10000  # Icon plus MB_SETFOREGROUND
            if ctypes.windll.user32.MessageBoxW(None, message, APP_NAME, flags):
                return
        except Exception:
            pass
    print(f"{APP_NAME}: {message}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
