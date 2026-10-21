from __future__ import annotations

import os
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppPaths:
    """Resolve all writable paths beneath the portable application root."""

    root: Path | None = None

    def __post_init__(self):
        if self.root is None:
            resolved = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[2]
            object.__setattr__(self, "root", resolved)
        else:
            object.__setattr__(self, "root", Path(self.root).resolve())

    @property
    def data(self) -> Path:
        return self.root / "data"

    @property
    def database(self) -> Path:
        return self.data / "bookledger.sqlite3"

    @property
    def photos(self) -> Path:
        return self.data / "photos"

    @property
    def trash(self) -> Path:
        return self.data / "trash"

    @property
    def assets(self) -> Path:
        return self.data / "assets"

    @property
    def backups(self) -> Path:
        return self.root / "backups"

    @property
    def user_config(self) -> Path:
        return self.assets

    @property
    def google_books_config(self) -> Path:
        return self.assets / "google_books.json"

    @property
    def provider_config(self) -> Path:
        return self.root / "config.json"

    @staticmethod
    def provider_config_fallback() -> Path:
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return Path(base) / "BookLedger" / "config.json"
        return Path.home() / ".config" / "BookLedger" / "config.json"

    @property
    def legacy_data(self) -> Path:
        return self.root / "BookLedger_Data"

    def prepare(self) -> None:
        """Migrate legacy files before the application can create a fresh database."""
        legacy_db = self.legacy_data / "bookledger.sqlite3"
        if self.database.exists() and legacy_db.exists():
            raise RuntimeError(
                f"Both portable and legacy databases exist. Resolve the conflict before starting: {self.database} and {legacy_db}"
            )
        for folder in (self.data, self.photos, self.trash, self.assets, self.backups):
            folder.mkdir(parents=True, exist_ok=True)
        if legacy_db.exists():
            self._migrate_legacy(legacy_db)
        # Prove the selected writable root is writable now, with a managed probe.
        probe = self.data / ".write-test"
        try:
            probe.write_bytes(b"")
            probe.unlink()
        except OSError as exc:
            raise RuntimeError(f"BookLedger cannot write to its data folder {self.data}: {exc}") from exc

    @staticmethod
    def _profile_google_books_config() -> Path | None:
        local_app_data = os.environ.get("LOCALAPPDATA")
        return Path(local_app_data) / "BookLedger" / "google_books.json" if local_app_data else None

    def _migrate_legacy(self, legacy_db: Path) -> None:
        """Copy and validate the old tree; keep it intact as a recovery source."""
        temp_root = Path(tempfile.mkdtemp(prefix=".bookledger-migration-", dir=self.data.parent))
        staged_db = temp_root / "bookledger.sqlite3"
        installed_files: list[Path] = []
        installed_backup_files: list[Path] = []
        try:
            source = sqlite3.connect(legacy_db)
            target = sqlite3.connect(staged_db)
            try:
                source.backup(target)
                target.commit()
            finally:
                target.close()
                source.close()
            for name in ("photos", "trash", "assets", "backups"):
                origin = self.legacy_data / name
                if origin.exists():
                    shutil.copytree(origin, temp_root / name, dirs_exist_ok=True)
            check = sqlite3.connect(staged_db)
            try:
                result = check.execute("PRAGMA integrity_check").fetchone()
                if not result or result[0] != "ok":
                    raise RuntimeError(f"Legacy database failed integrity verification: {result[0] if result else 'no result'}")
                foreign = check.execute("PRAGMA foreign_key_check").fetchall()
                if foreign:
                    raise RuntimeError(f"Legacy database has {len(foreign)} foreign-key violation(s); source was left untouched.")
            finally:
                check.close()
            # Only install into empty destinations. A pre-existing partial data tree
            # is not silently overwritten; it may need manual recovery.
            if self.database.exists() or any(
                path.exists() and any(path.iterdir()) for path in (self.photos, self.trash, self.assets)
            ):
                raise RuntimeError("Legacy migration found existing portable data files. Resolve the destination conflict before starting.")
            self.database.parent.mkdir(parents=True, exist_ok=True)
            for name in ("photos", "trash", "assets"):
                staged = temp_root / name
                if staged.exists():
                    for item in staged.rglob("*"):
                        if not item.is_file():
                            continue
                        relative = item.relative_to(staged)
                        destination = self.data / name / relative
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(item, destination)
                        installed_files.append(destination)
                elif name in ("photos", "trash", "assets"):
                    (self.data / name).mkdir(exist_ok=True)
            legacy_backups = temp_root / "backups"
            if legacy_backups.exists():
                for backup in legacy_backups.iterdir():
                    target = self.backups / backup.name
                    if target.exists():
                        target = self.backups / f"legacy-{datetime.now():%Y%m%d%H%M%S}-{backup.name}"
                    if backup.is_dir():
                        shutil.copytree(backup, target)
                    else:
                        shutil.copy2(backup, target)
                    installed_backup_files.extend(target.rglob("*") if target.is_dir() else [target])
            staged_db.replace(self.database)
            # Verify the installed copy as well. The legacy source is intentionally
            # retained so migration never destroys the only recoverable source.
            verify = sqlite3.connect(self.database)
            try:
                result = verify.execute("PRAGMA integrity_check").fetchone()
                if not result or result[0] != "ok":
                    raise RuntimeError("Migrated database failed final verification; legacy source remains available.")
            finally:
                verify.close()
        except Exception:
            # Remove only files installed by this migration; keep source and backups.
            if self.database.exists():
                self.database.unlink()
            for item in reversed(installed_files + installed_backup_files):
                try:
                    if item.is_file():
                        item.unlink()
                except OSError:
                    pass
            raise
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

    def migrate_legacy_photos(self, db) -> None:
        """Canonicalize old referenced photos only after their bytes are copied safely."""
        from bookledger.services.photos import PhotoService

        photo_service = PhotoService(self.photos, self.trash)
        with db.connect() as conn:
            rows = conn.execute("SELECT id,photo_path FROM copies ORDER BY id").fetchall()
        for row in rows:
            copy_id = int(row["id"])
            expected = f"photos/{copy_id}.jpg"
            if row["photo_path"] == expected and (self.photos / f"{copy_id}.jpg").is_file():
                continue
            raw = Path(str(row["photo_path"]))
            source = raw if raw.is_absolute() else self.data / raw
            source = source.resolve()
            try:
                source.relative_to(self.data.resolve())
            except ValueError as exc:
                raise RuntimeError(f"Copy ID {copy_id} references a photo outside portable data: {row['photo_path']}") from exc
            if not source.is_file():
                raise RuntimeError(f"Copy ID {copy_id} references a missing legacy photo: {source}")
            with db.connect() as conn:
                pending = conn.execute("SELECT 1 FROM storage_operations WHERE operation='migrate' AND copy_id=?", (copy_id,)).fetchone()
            if pending:
                continue
            target = self.photos / f"{copy_id}.jpg"
            if target.exists():
                raise RuntimeError(f"Cannot migrate Copy ID {copy_id}; canonical photo path already exists: {target}")
            staged = photo_service.import_and_compress(source)
            with db.connect() as conn:
                conn.execute("INSERT INTO storage_operations(operation,copy_id,source_path,target_path,state) VALUES('migrate',?,?,?,'prepared')",
                             (copy_id, staged.relative_to(self.data).as_posix(), expected))
            try:
                photo_service.install(copy_id, staged)
                with db.connect() as conn:
                    conn.execute("BEGIN IMMEDIATE")
                    conn.execute("UPDATE copies SET photo_path=? WHERE id=?", (expected, copy_id))
                    conn.execute("DELETE FROM storage_operations WHERE operation='migrate' AND copy_id=?", (copy_id,))
            except Exception:
                raise

    def finalize_legacy_migration(self) -> Path | None:
        """Retain the verified legacy tree under a recovery name to prevent reimport."""
        if not self.legacy_data.exists():
            return None
        destination = self.root / "BookLedger_Data.migrated"
        if destination.exists():
            destination = self.root / f"BookLedger_Data.migrated-{datetime.now():%Y%m%d%H%M%S}"
        self.legacy_data.replace(destination)
        return destination
