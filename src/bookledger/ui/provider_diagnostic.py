from __future__ import annotations

import time
import threading
import tkinter as tk
from queue import Empty, SimpleQueue
from tkinter import ttk

from bookledger.provider_registry import PROVIDER_REGISTRY
from bookledger.services.metadata_contract import MetadataResult, failure_kind


DIAGNOSTIC_TIMEOUT_SECONDS = 5.0
FIELD_DEFINITIONS = (
    ("Title", "title"),
    ("Author", "author"),
    ("Genre", "genre"),
    ("Publisher", "publisher"),
    ("Year", "publication_year"),
    ("Edition", "edition"),
    ("Pages", "page_count"),
    ("SRP", "srp"),
    ("Book Details", "book_details"),
)
FIELD_COLORS = {"OK": "#18723a", "No Data": "#b42318", "N/A": "#64748b", "—": "#64748b"}
TIME_FAST_COLOR = "#18723a"
TIME_SLOW_COLOR = "#b42318"


def diagnostic_field_statuses(result: MetadataResult, supported_fields) -> dict[str, str]:
    supported_fields = frozenset(supported_fields)
    statuses = {}
    for label, field in FIELD_DEFINITIONS:
        if field not in supported_fields:
            statuses[label] = "N/A"
        elif _has_field_value(result.values.get(field)):
            statuses[label] = "OK"
        else:
            statuses[label] = "No Data"
    return statuses


def _has_field_value(value) -> bool:
    return value is not None and (not isinstance(value, str) or bool(value.strip()))


def diagnostic_overall_status(result: MetadataResult, supported_fields) -> str:
    if result.failure_kind == "timeout":
        return "Timeout"
    if result.failure_kind == "provider":
        return "HTTP error"
    if result.status == "Lookup failed" or result.failure_kind in {"unexpected", "network", "unverified"}:
        return "Lookup error"
    if result.status == "No data" and result.record_found is False:
        return "ISBN not found"
    if result.status == "Retrieved" or (result.status == "No data" and result.record_found is True):
        supported_fields = frozenset(supported_fields)
        if all(_has_field_value(result.values.get(field)) for field in supported_fields):
            return "Completed"
        return "Partial data"
    return "Lookup error"


def elapsed_color(elapsed_seconds: float) -> str:
    return TIME_FAST_COLOR if elapsed_seconds <= 3.0 else TIME_SLOW_COLOR


class MetadataProviderTestDialog(tk.Toplevel):
    """Run one registered metadata adapter without saving or merging a book."""

    def __init__(self, parent, *, google_books_api_key: str = "", providers=None):
        super().__init__(parent)
        self._providers = tuple(
            descriptor for descriptor in (providers if providers is not None else PROVIDER_REGISTRY)
        )
        self._providers_by_name = {descriptor.name: descriptor for descriptor in self._providers}
        self._google_books_api_key = google_books_api_key
        self._operation_id = 0
        self._busy = False
        self._destroyed = False
        self._started_at = None
        self._timeout_after_id = None
        self._poll_after_id = None
        self._ui_queue = SimpleQueue()
        self._field_status_vars: dict[str, tk.StringVar] = {}
        self._field_status_labels = {}

        self.title("ISBN Lookup Test")
        self.geometry("500x560")
        self.minsize(420, 500)
        self.transient(parent)
        self.grab_set()

        self.isbn_var = tk.StringVar(value="")
        self.provider_var = tk.StringVar(value=self._providers[0].name if self._providers else "")
        self.overall_status_var = tk.StringVar(value="Ready")
        self.fetch_time_var = tk.StringVar(value="—")
        self.validation_var = tk.StringVar(value="")
        self._build()
        self.protocol("WM_DELETE_WINDOW", self._request_close)
        self.bind("<Return>", self._block_enter_submission)
        self.bind("<KP_Enter>", self._block_enter_submission)
        self.bind("<Destroy>", self._on_destroy, add="+")
        self._poll_after_id = self.after(40, self._poll_worker_results)

    def _build(self):
        frame = ttk.Frame(self, padding=16)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Provider").grid(row=0, column=0, sticky="w", padx=(0, 10), pady=4)
        self.provider_combo = ttk.Combobox(
            frame,
            textvariable=self.provider_var,
            values=tuple(descriptor.name for descriptor in self._providers),
            state="readonly",
        )
        self.provider_combo.grid(row=0, column=1, sticky="ew", pady=4)
        self.provider_combo.bind("<<ComboboxSelected>>", self._provider_changed)

        ttk.Label(frame, text="ISBN").grid(row=1, column=0, sticky="w", padx=(0, 10), pady=4)
        self.isbn_entry = ttk.Entry(frame, textvariable=self.isbn_var)
        self.isbn_entry.grid(row=1, column=1, sticky="ew", pady=4)
        self.isbn_entry.bind("<KeyRelease>", lambda _event: self.validation_var.set(""))

        self.validation_label = ttk.Label(frame, textvariable=self.validation_var, foreground="#b42318")
        self.validation_label.grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, 4))

        fields = ttk.LabelFrame(frame, text="Field Results", padding=(12, 8))
        fields.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(6, 12))
        fields.columnconfigure(1, weight=1)
        for row, (label, _field) in enumerate(FIELD_DEFINITIONS):
            ttk.Label(fields, text=label).grid(row=row, column=0, sticky="w", padx=(0, 20), pady=2)
            status_var = tk.StringVar(value="—")
            status_label = ttk.Label(fields, textvariable=status_var, foreground=FIELD_COLORS["—"])
            status_label.grid(row=row, column=1, sticky="w", pady=2)
            self._field_status_vars[label] = status_var
            self._field_status_labels[label] = status_label

        summary = ttk.Frame(frame)
        summary.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        summary.columnconfigure(1, weight=1)
        ttk.Label(summary, text="Overall Status").grid(row=0, column=0, sticky="w", padx=(0, 10), pady=3)
        ttk.Label(summary, textvariable=self.overall_status_var).grid(row=0, column=1, sticky="w", pady=3)
        ttk.Label(summary, text="Fetch Time").grid(row=1, column=0, sticky="w", padx=(0, 10), pady=3)
        self.fetch_time_label = ttk.Label(summary, textvariable=self.fetch_time_var, foreground="#64748b")
        self.fetch_time_label.grid(row=1, column=1, sticky="w", pady=3)

        controls = ttk.Frame(frame)
        controls.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        self.test_button = ttk.Button(controls, text="Test", command=self._start_test)
        self.test_button.pack(side="left")
        self.clear_button = ttk.Button(controls, text="Clear", command=self.clear)
        self.clear_button.pack(side="left", padx=(8, 0))
        self.close_button = ttk.Button(controls, text="Close", command=self._request_close)
        self.close_button.pack(side="right")

    def _block_enter_submission(self, _event=None):
        # Tests are started only by the explicit button, preventing duplicate
        # submissions from Return bindings while a lookup is already running.
        return "break"

    def _provider_changed(self, _event=None):
        if not self._busy:
            self._reset_results(clear_isbn=True)

    def _reset_results(self, *, clear_isbn: bool):
        if clear_isbn:
            self.isbn_var.set("")
        self.validation_var.set("")
        self.overall_status_var.set("Ready")
        self.fetch_time_var.set("—")
        self.fetch_time_label.configure(foreground="#64748b")
        for label, status_var in self._field_status_vars.items():
            status_var.set("—")
            self._field_status_labels[label].configure(foreground=FIELD_COLORS["—"])

    def clear(self):
        if self._busy:
            return
        self._reset_results(clear_isbn=True)

    def _set_busy(self, busy: bool):
        self._busy = busy
        self.test_button.configure(state="disabled" if busy else "normal")
        self.clear_button.configure(state="disabled" if busy else "normal")
        self.close_button.configure(state="disabled" if busy else "normal")
        self.isbn_entry.configure(state="disabled" if busy else "normal")
        self.provider_combo.configure(state="disabled" if busy else "readonly")

    def _start_test(self):
        if self._busy or self._destroyed:
            return
        isbn = self.isbn_var.get().strip()
        if not isbn:
            self.validation_var.set("Enter an ISBN before starting the test.")
            self.isbn_entry.focus_set()
            return
        descriptor = self._providers_by_name.get(self.provider_var.get())
        if descriptor is None:
            self.validation_var.set("Select a metadata provider.")
            return
        if not descriptor.implemented:
            result = MetadataResult("Lookup failed", {}, descriptor.name, "Provider is not implemented", "unexpected")
            statuses = diagnostic_field_statuses(result, descriptor.supported_fields)
            for label, status in statuses.items():
                self._field_status_vars[label].set(status)
                self._field_status_labels[label].configure(foreground=FIELD_COLORS[status])
            self.overall_status_var.set("Lookup error")
            self.fetch_time_var.set("0.00 seconds")
            self.fetch_time_label.configure(foreground=elapsed_color(0.0))
            return

        self._operation_id += 1
        operation_id = self._operation_id
        self._started_at = time.monotonic()
        self.validation_var.set("")
        self.overall_status_var.set("Retrieving data")
        self.fetch_time_var.set("—")
        self.fetch_time_label.configure(foreground="#64748b")
        for label, status_var in self._field_status_vars.items():
            status_var.set("—")
            self._field_status_labels[label].configure(foreground=FIELD_COLORS["—"])
        self._set_busy(True)
        self._timeout_after_id = self.after(
            int(DIAGNOSTIC_TIMEOUT_SECONDS * 1000),
            lambda: self._finish_timeout(operation_id, descriptor),
        )

        started_at = self._started_at
        api_key = self._google_books_api_key

        def work():
            try:
                provider = descriptor.factory(api_key)
                # Providers are freshly instantiated, so the diagnostic's
                # budget cannot mutate normal intake or another lookup.
                provider.timeout = DIAGNOSTIC_TIMEOUT_SECONDS
                result = provider.lookup(isbn)
                if not isinstance(result, MetadataResult):
                    raise TypeError("Provider returned an unexpected result")
                if not isinstance(result.values, dict):
                    raise TypeError("Provider returned an invalid metadata mapping")
            except Exception as exc:
                result = MetadataResult(
                    "Lookup failed", {}, descriptor.name, str(exc), failure_kind(exc)
                )
            elapsed = max(time.monotonic() - started_at, 0.0)
            self._ui_queue.put((operation_id, descriptor, result, elapsed))

        try:
            threading.Thread(target=work, name="BookLedgerProviderDiagnostic", daemon=True).start()
        except Exception as exc:
            elapsed = max(time.monotonic() - started_at, 0.0)
            result = MetadataResult("Lookup failed", {}, descriptor.name, str(exc), failure_kind(exc))
            self._finish_result(operation_id, descriptor, result, elapsed)

    def _poll_worker_results(self):
        if self._destroyed:
            return
        self._drain_worker_results()
        try:
            self._poll_after_id = self.after(40, self._poll_worker_results)
        except tk.TclError:
            self._destroyed = True

    def _drain_worker_results(self):
        try:
            while True:
                operation_id, descriptor, result, elapsed = self._ui_queue.get_nowait()
                self._finish_result(operation_id, descriptor, result, elapsed)
        except Empty:
            pass
        except tk.TclError:
            self._destroyed = True

    def _cancel_timeout(self):
        if self._timeout_after_id is not None:
            try:
                self.after_cancel(self._timeout_after_id)
            except tk.TclError:
                pass
            self._timeout_after_id = None

    def _finish_timeout(self, operation_id, descriptor):
        if self._destroyed or not self._busy or operation_id != self._operation_id:
            return
        # If the UI event loop was busy near the deadline, process any worker
        # result already waiting before declaring the operation timed out.
        self._drain_worker_results()
        if self._destroyed or not self._busy or operation_id != self._operation_id:
            return
        elapsed = max(time.monotonic() - self._started_at, DIAGNOSTIC_TIMEOUT_SECONDS)
        result = MetadataResult("Lookup failed", {}, descriptor.name, "Diagnostic lookup timed out", "timeout")
        self._finish_result(operation_id, descriptor, result, elapsed)

    def _finish_result(self, operation_id, descriptor, result, elapsed):
        if self._destroyed or not self._busy or operation_id != self._operation_id:
            return
        self._cancel_timeout()
        supported_fields = frozenset(descriptor.supported_fields)
        statuses = diagnostic_field_statuses(result, supported_fields)
        for label, status in statuses.items():
            self._field_status_vars[label].set(status)
            self._field_status_labels[label].configure(foreground=FIELD_COLORS[status])
        self.overall_status_var.set(diagnostic_overall_status(result, supported_fields))
        self.fetch_time_var.set(f"{elapsed:.2f} seconds")
        self.fetch_time_label.configure(foreground=elapsed_color(elapsed))
        self._set_busy(False)

    def _request_close(self):
        if not self._busy and not self._destroyed:
            self.destroy()

    def _on_destroy(self, event):
        if event.widget is not self:
            return
        self._destroyed = True
        self._operation_id += 1
        self._cancel_timeout()
        if self._poll_after_id is not None:
            try:
                self.after_cancel(self._poll_after_id)
            except tk.TclError:
                pass
            self._poll_after_id = None
