"""Explicit update checks with all Tk access confined to the UI thread."""

from queue import Empty, SimpleQueue
import threading
import tkinter as tk
from tkinter import ttk, font as tkfont
import webbrowser

from bookledger import __version__
from bookledger.services.updates import UpdateResult, check_for_updates, desktop_package


class TextLink(ttk.Label):
    def __init__(self, parent, command, *, text="Check for Updates"):
        self._link_font = tkfont.nametofont("TkDefaultFont").copy()
        self._link_font.configure(underline=True)
        super().__init__(parent, text=text, cursor="hand2", takefocus=True, font=self._link_font)
        self.command = command
        self.bind("<Button-1>", self._activate)
        self.bind("<Return>", self._activate)
        self.bind("<space>", self._activate)
        self.bind("<Enter>", lambda _e: self._link_font.configure(weight="bold"))
        self.bind("<Leave>", lambda _e: self._link_font.configure(weight="bold" if self.focus_get() is self else "normal"))
        self.bind("<FocusIn>", lambda _e: self._link_font.configure(weight="bold"))
        self.bind("<FocusOut>", lambda _e: self._link_font.configure(weight="normal"))
        self.bind("<<ThemeChanged>>", self._theme_color)
        self._theme_color()

    def _theme_color(self, _event=None):
        colors = getattr(getattr(self.winfo_toplevel(), "style", None), "colors", None)
        color = colors.info if colors else ttk.Style(self).lookup("TLabel", "foreground")
        self.configure(foreground=color)

    def _activate(self, _event=None):
        self.command()
        return "break"


class UpdateDialog(tk.Toplevel):
    def __init__(self, parent, *, checker=check_for_updates, package=None):
        super().__init__(parent)
        self.title("BookLedger Updates")
        self.transient(parent)
        self.geometry("650x470")
        self.minsize(420, 320)
        self._checker = checker
        self._package = package if package is not None else desktop_package()
        self._results = SimpleQueue()
        self._poll_id = None
        self._busy = False
        self._release_url = None
        body = ttk.Frame(self, padding=14)
        body.pack(fill="both", expand=True)
        self.state_text = tk.StringVar()
        self.versions = tk.StringVar(value=f"Installed: {__version__}    Available: checking…")
        self.message = tk.StringVar()
        ttk.Label(body, textvariable=self.state_text, font=("Segoe UI", 13, "bold")).pack(anchor="w")
        ttk.Label(body, textvariable=self.versions).pack(anchor="w", pady=6)
        ttk.Label(body, textvariable=self.message, wraplength=590).pack(fill="x", pady=(0, 8))
        notes_panel = ttk.Frame(body)
        notes_panel.pack(fill="both", expand=True)
        self.notes = tk.Text(notes_panel, wrap="word", height=8, state="disabled")
        scroll = ttk.Scrollbar(notes_panel, command=self.notes.yview)
        self.notes.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.notes.pack(fill="both", expand=True)
        actions = ttk.Frame(body)
        actions.pack(fill="x", pady=(10, 0))
        self.retry = ttk.Button(actions, text="Check Again", command=self.start)
        self.retry.pack(side="left")
        self.release = ttk.Button(actions, text="Open Release Page", command=self._open_release, state="disabled")
        self.release.pack(side="left", padx=8)
        ttk.Button(actions, text="Close", command=self.destroy).pack(side="right")
        self.bind("<Escape>", lambda _event: self.destroy())
        self.protocol("WM_DELETE_WINDOW", self.destroy)
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
            self.after_cancel(self._poll_id)
            self._poll_id = None
        super().destroy()
