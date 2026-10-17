from __future__ import annotations
import sys
import os
from pathlib import Path


def app_root() -> Path:
    """Directory containing the portable app, or project root when run from source."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


class AppPaths:
    def __init__(self, root: str | Path | None = None):
        self.root = Path(root) if root else app_root()
        self.data = self.root / "BookLedger_Data"
        self.photos = self.data / "photos"
        self.backups = self.data / "backups"
        self.database = self.data / "bookledger.sqlite3"
        config_root = Path(os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config"))
        self.user_config = config_root / "BookLedger"
        self.google_books_config = self.user_config / "google_books.json"
        for directory in (self.data, self.photos, self.backups):
            directory.mkdir(parents=True, exist_ok=True)
