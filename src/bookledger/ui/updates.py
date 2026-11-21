"""Explicit update checks with all Tk access confined to the UI thread."""

from pathlib import Path
from queue import Empty, SimpleQueue
import threading
import tkinter as tk
from tkinter import ttk
import webbrowser

from bookledger import __version__
from bookledger.services.update_download import DownloadCancelled, download_update, update_staging_directory
from bookledger.services.updates import UpdateResult, check_for_updates, desktop_package


class UpdatePage(ttk.Frame):
    def __init__(self, parent, *, checker=check_for_updates, package=None, downloader=download_update, staging=None):
        super().__init__(parent, padding=14)
        self._checker = checker
        self._downloader = downloader
        self._staging = staging
        self._package = package if package is not None else desktop_package()
        self._results = SimpleQueue()
        self._poll_id = None
        self._busy = False
        self._download_cancel = None
        self._download_poll_id = None
        self._download_events = SimpleQueue()
        self._current_result = None
        self._verified_path = None
        self._release_url = None
        self.state_text = tk.StringVar()
        self.versions = tk.StringVar(value=f"Installed: {__version__}    Available: checking…")
        self.message = tk.StringVar()
        self.download_status = tk.StringVar()
        ttk.Label(self, textvariable=self.state_text, font=("Segoe UI", 13, "bold")).pack(anchor="w")
        ttk.Label(self, textvariable=self.versions).pack(anchor="w", pady=6)
        ttk.Label(self, textvariable=self.message, wraplength=720).pack(fill="x", pady=(0, 8))
        notes_panel = ttk.Frame(self)
        notes_panel.pack(fill="both", expand=True)
        style = ttk.Style(self)
        note_foreground = style.lookup("TLabel", "foreground") or "black"
        self.notes = tk.Text(
            notes_panel,
            wrap="word",
            height=8,
            state="disabled",
            background=style.lookup("TFrame", "background") or "white",
            foreground=note_foreground,
            insertbackground=note_foreground,
        )
        scroll = ttk.Scrollbar(notes_panel, command=self.notes.yview)
        self.notes.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.notes.pack(fill="both", expand=True)
        self.download_status_label = ttk.Label(self, textvariable=self.download_status, wraplength=720)
        self.download_progress = ttk.Progressbar(self, mode="determinate", maximum=100)
        actions = ttk.Frame(self)
        actions.pack(fill="x", side="bottom", pady=(10, 0))
        self.retry = ttk.Button(actions, text="Check Again", command=self.start)
        self.retry.pack(side="left")
        self.release = ttk.Button(actions, text="Open Release Page", command=self._open_release, state="disabled")
        self.release.pack(side="left", padx=8)
        self.download = ttk.Button(actions, text="Download & Verify", command=self._download, state="disabled")
        self.download.pack(side="left")
        self.cancel_download = ttk.Button(actions, text="Cancel Download", command=self._cancel_download, state="disabled")
        self.cancel_download.pack(side="left", padx=8)
        self.open_download_folder = ttk.Button(actions, text="Open Download Folder", command=self._open_download_folder, state="disabled")
        self.open_download_folder.pack(side="left")
        self.start()

    def start(self):
        if self._busy:
            return
        self._busy = True
        self._release_url = None
        self._current_result = None
        self._verified_path = None
        self.download.configure(state="disabled")
        self.open_download_folder.configure(state="disabled")
        self.download_status.set("")
        self.download_status_label.pack_forget()
        self.download_progress.pack_forget()
        self.state_text.set("Checking…")
        self.versions.set(f"Installed: {__version__}    Available: checking…")
        self.message.set("Contacting the official BookLedger GitHub release service…")
        self.retry.configure(state="disabled")
        self.release.configure(state="disabled")
        results, checker, package = self._results, self._checker, self._package

        def work():
            try:
                result = checker(__version__, package)
            except Exception:
                result = UpdateResult("Unable to Check", __version__, message="The release check could not finish. Try again.")
            results.put(result)

        threading.Thread(target=work, daemon=True).start()
        self._poll_id = self.after(50, self._poll)

    def _poll(self):
        self._poll_id = None
        try:
            result = self._results.get_nowait()
        except Empty:
            self._poll_id = self.after(50, self._poll)
            return
        self._busy = False
        self.state_text.set(result.state)
        self.versions.set(f"Installed: {result.installed}    Available: {result.available or 'unknown'}")
        self.message.set(result.message)
        self.notes.configure(state="normal")
        self.notes.delete("1.0", "end")
        self.notes.insert("1.0", result.notes or "No release notes available.")
        self.notes.configure(state="disabled")
        self._release_url = result.release_url
        self._current_result = result
        self.retry.configure(state="normal")
        self.release.configure(state="normal" if self._release_url else "disabled")
        self.download.configure(state="normal" if self._package in {"Portable", "Fallback"} and result.state == "Update Available" and result.asset_name else "disabled")
        if self._package in {"Portable", "Fallback"} and result.state == "Update Available" and result.asset_name:
            self.download_status.set(f"{result.asset_name} · {result.asset_size:,} bytes")
            self.download_status_label.pack(fill="x", pady=(8, 0), before=self.notes.master)

    def _download(self):
        result = self._current_result
        if self._download_cancel is not None or result is None or str(self.download.cget("state")) != "normal":
            return
        cancel = threading.Event()
        self._download_cancel = cancel
        self._verified_path = None
        self.download.configure(state="disabled")
        self.cancel_download.configure(state="normal")
        self.retry.configure(state="disabled")
        self.download_status_label.pack(fill="x", pady=(8, 0), before=self.notes.master)
        self.download_progress.pack(fill="x", pady=(4, 0), before=self.notes.master)
        self.download_status.set(f"Downloading {result.asset_name}…")
        self.download_progress.configure(value=0, maximum=result.asset_size or 100)
        events, downloader, staging = self._download_events, self._downloader, self._staging

        def work():
            try:
                path = downloader(result, cancel, staging=staging, progress=lambda state, done, total: events.put(("progress", state, done, total)))
                events.put(("verified", path))
            except DownloadCancelled:
                events.put(("canceled",))
            except Exception as exc:
                events.put(("failed", str(exc)))

        threading.Thread(target=work, daemon=True).start()
        self._download_poll_id = self.after(50, self._poll_download)

    def _poll_download(self):
        self._download_poll_id = None
        try:
            event = self._download_events.get_nowait()
        except Empty:
            if self._download_cancel is not None:
                self._download_poll_id = self.after(50, self._poll_download)
            return
        kind, *data = event
        if kind == "progress":
            state, done, total = data
            if state == "Verifying":
                self.download_status.set("Verifying SHA-256 and package contents…")
            else:
                self.download_status.set(f"Downloading {done:,} of {total:,} bytes…")
                self.download_progress.configure(value=done, maximum=total)
            self._download_poll_id = self.after(50, self._poll_download)
            return
        self._download_cancel = None
        self.cancel_download.configure(state="disabled")
        self.retry.configure(state="normal")
        if kind == "verified":
            self._verified_path = Path(data[0])
            self.state_text.set("Verified Download")
            self.download_status.set(f"Verified {self._verified_path.name}\nSaved to {self._verified_path}\nInstallation is not available yet.")
            self.open_download_folder.configure(state="normal")
        elif kind == "canceled":
            self.state_text.set("Canceled")
            self.download_status.set("The download was canceled. No incomplete file was retained.")
            self.download.configure(state="normal" if self._current_result and self._current_result.state == "Update Available" else "disabled")
        else:
            self.state_text.set("Failed")
            self.download_status.set(f"The update could not be verified: {data[0]}")
            self.download.configure(state="normal" if self._current_result and self._current_result.state == "Update Available" else "disabled")

    def _cancel_download(self):
        if self._download_cancel is not None:
            self._download_cancel.set()
            self.cancel_download.configure(state="disabled")
            self.download_status.set("Canceling download…")

    def _open_download_folder(self):
        if self._verified_path is not None:
            try:
                import os
                os.startfile(self._verified_path.parent)
            except (AttributeError, OSError):
                self.download_status.set(f"Open this verified file in File Explorer: {self._verified_path}")

    def _open_release(self):
        if self._release_url:
            try:
                if not webbrowser.open(self._release_url):
                    self.message.set("Could not open a browser. Try again or visit the repository's Releases page.")
            except (OSError, webbrowser.Error):
                self.message.set("Could not open a browser. Visit the repository's Releases page.")

    def destroy(self):
        if self._download_cancel is not None:
            self._download_cancel.set()
        if self._download_poll_id is not None:
            try:
                self.after_cancel(self._download_poll_id)
            except tk.TclError:
                pass
            self._download_poll_id = None
        if self._poll_id is not None:
            try:
                self.after_cancel(self._poll_id)
            except tk.TclError:
                pass
            self._poll_id = None
        super().destroy()
