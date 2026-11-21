"""Explicit update checks with all Tk access confined to the UI thread."""

from queue import Empty, SimpleQueue
import threading
import tkinter as tk
from tkinter import ttk
import webbrowser

from bookledger import __version__
from bookledger.services.updates import UpdateResult, check_for_updates, desktop_package


class UpdatePage(ttk.Frame):
    def __init__(self, parent, *, checker=check_for_updates, package=None):
        super().__init__(parent, padding=14)
        self._checker = checker
        self._package = package if package is not None else desktop_package()
        self._results = SimpleQueue()
        self._poll_id = None
        self._busy = False
        self._release_url = None
        self.state_text = tk.StringVar()
        self.versions = tk.StringVar(value=f"Installed: {__version__}    Available: checking…")
        self.message = tk.StringVar()
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
        actions = ttk.Frame(self)
        actions.pack(fill="x", side="bottom", pady=(10, 0))
        self.retry = ttk.Button(actions, text="Check Again", command=self.start)
        self.retry.pack(side="left")
        self.release = ttk.Button(actions, text="Open Release Page", command=self._open_release, state="disabled")
        self.release.pack(side="left", padx=8)
        self.start()

    def start(self):
        if self._busy:
            return
        self._busy = True
        self._release_url = None
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
        self.retry.configure(state="normal")
        self.release.configure(state="normal" if self._release_url else "disabled")

    def _open_release(self):
        if self._release_url:
            try:
                if not webbrowser.open(self._release_url):
                    self.message.set("Could not open a browser. Try again or visit the repository's Releases page.")
            except (OSError, webbrowser.Error):
                self.message.set("Could not open a browser. Visit the repository's Releases page.")

    def destroy(self):
        if self._poll_id is not None:
            try:
                self.after_cancel(self._poll_id)
            except tk.TclError:
                pass
            self._poll_id = None
        super().destroy()
