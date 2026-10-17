from __future__ import annotations
from datetime import datetime
from pathlib import Path
import shutil
import sqlite3
import zipfile
from bookledger.db.database import Database


class BackupService:
    """Create portable, self-contained backup archives with a consistent SQLite snapshot."""
    def __init__(self, db: Database, data_dir: str | Path, backup_dir: str | Path):
        self.db = db
        self.data_dir = Path(data_dir)
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def create_backup(self) -> Path:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        target = self.backup_dir / f"BookLedger-backup-{stamp}.zip"
        staging = self.backup_dir / f".staging-{stamp}"
        staging.mkdir()
        try:
            snapshot = staging / "bookledger.sqlite3"
            self.db.backup_to(snapshot)
            ok, message = Database(snapshot).integrity_check()
            if not ok:
                raise RuntimeError(f"Database integrity check failed: {message}")
            with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
                archive.write(snapshot, "bookledger.sqlite3")
                photo_dir = self.data_dir / "photos"
                if photo_dir.exists():
                    for photo in photo_dir.rglob("*"):
                        if photo.is_file():
                            archive.write(photo, str(Path("photos") / photo.relative_to(photo_dir)))
                archive.writestr("BACKUP_INFO.txt", f"BookLedger backup\nCreated: {datetime.now().isoformat(timespec='seconds')}\nContains database snapshot and stored copy photos.\n")
            return target
        finally:
            shutil.rmtree(staging, ignore_errors=True)

    def verify_archive(self, archive_path: str | Path) -> tuple[bool, str]:
        try:
            with zipfile.ZipFile(archive_path, "r") as archive:
                bad = archive.testzip()
                if bad:
                    return False, f"Corrupt archive member: {bad}"
                if "bookledger.sqlite3" not in archive.namelist():
                    return False, "The archive does not contain a database snapshot."
                import tempfile
                with tempfile.TemporaryDirectory() as temp:
                    extracted = Path(temp) / "bookledger.sqlite3"
                    extracted.write_bytes(archive.read("bookledger.sqlite3"))
                    return Database(extracted).integrity_check()
        except Exception as exc:
            return False, str(exc)

    def restore_backup(self, archive_path: str | Path) -> None:
        """Restore database and photos from a verified archive. Caller must confirm with user."""
        archive_path = Path(archive_path)
        ok, message = self.verify_archive(archive_path)
        if not ok:
            raise ValueError(f"Backup verification failed: {message}")
        import tempfile
        staging_parent = self.data_dir.parent / f".bookledger-restore-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        staged_photos = staging_parent / "photos"
        staged_photos.mkdir(parents=True, exist_ok=True)
        staged_db = staging_parent / "bookledger.sqlite3"
        try:
            with zipfile.ZipFile(archive_path, "r") as archive:
                for member in archive.namelist():
                    member_path = Path(member)
                    if member_path.is_absolute() or ".." in member_path.parts:
                        raise ValueError("The backup contains an unsafe file path.")
                    if member == "bookledger.sqlite3":
                        staged_db.write_bytes(archive.read(member))
                    elif member.startswith("photos/") and not member.endswith("/"):
                        relative = member_path.relative_to("photos")
                        destination = staged_photos / relative
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        destination.write_bytes(archive.read(member))
            ok, message = Database(staged_db).integrity_check()
            if not ok:
                raise ValueError(f"Restored database integrity check failed: {message}")
            # Keep a safety snapshot before replacing live data.
            self.create_backup()
            live_db = self.db.path
            live_photos = self.data_dir / "photos"
            replacement_db = self.data_dir / "bookledger.restore.tmp"
            old_db = self.data_dir / "bookledger.sqlite3.pre-restore"
            old_photos = self.data_dir / "photos.pre-restore"
            shutil.copy2(staged_db, replacement_db)
            if old_db.exists():
                old_db.unlink()
            if old_photos.exists():
                shutil.rmtree(old_photos)
            db_moved = photos_moved = new_db_installed = new_photos_installed = False
            try:
                if live_db.exists():
                    live_db.replace(old_db)
                    db_moved = True
                if live_photos.exists():
                    live_photos.replace(old_photos)
                    photos_moved = True
                replacement_db.replace(live_db)
                new_db_installed = True
                staged_photos.replace(live_photos)
                new_photos_installed = True
            except Exception:
                if new_photos_installed and live_photos.exists():
                    shutil.rmtree(live_photos, ignore_errors=True)
                if photos_moved and old_photos.exists():
                    old_photos.replace(live_photos)
                if new_db_installed and live_db.exists():
                    live_db.unlink()
                if db_moved and old_db.exists():
                    old_db.replace(live_db)
                raise
            old_db.unlink(missing_ok=True)
            shutil.rmtree(old_photos, ignore_errors=True)
        finally:
            shutil.rmtree(staging_parent, ignore_errors=True)
