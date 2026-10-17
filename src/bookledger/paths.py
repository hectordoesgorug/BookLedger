from __future__ import annotations
import sys
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
        for directory in (self.data, self.photos, self.backups):
            directory.mkdir(parents=True, exist_ok=True)
