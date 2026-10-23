from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import stat
import uuid
import zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath

from bookledger.db.database import SCHEMA_VERSION, Database


class BackupService:
    """Complete portable library snapshots and recoverable snapshot replacement."""

    MANIFEST = "manifest.json"
    DB_MEMBER = "data/bookledger.sqlite3"
    COMPONENTS = ("database", "photos", "trash", "assets", "config")

    def __init__(self, db: Database, data_dir: str | Path, backup_dir: str | Path, config_path: str | Path | None = None):
        self.db = db
        self.data_dir = Path(data_dir).resolve()
        self.backup_dir = Path(backup_dir).resolve()
        self.config_path = Path(config_path).resolve() if config_path else self.data_dir.parent / "config.json"
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.latest_recovery_point: Path | None = None

    def create_backup(self) -> Path:
        """Write and validate a collision-safe archive before publishing it."""
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        target = self.backup_dir / f"BookLedger-backup-{stamp}-{uuid.uuid4().hex[:8]}.zip"
        while target.exists():
            target = self.backup_dir / f"BookLedger-backup-{stamp}-{uuid.uuid4().hex[:8]}.zip"
        partial = self.backup_dir / f".partial-{uuid.uuid4().hex}.zip"
        with self.db.operation_guard():
            try:
                with zipfile.ZipFile(partial, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
                    manifest = {"format": "bookledger-snapshot", "version": 1, "created_at": datetime.now().astimezone().isoformat(timespec="seconds"), "files": {}}
                    self._add_file(archive, manifest, self.db.path, self.DB_MEMBER)
                    for directory in ("photos", "trash", "assets"):
                        source = self.data_dir / directory
                        if source.exists():
                            self._add_tree(archive, manifest, source, f"data/{directory}")
                    config_bytes = self.config_path.read_bytes() if self.config_path.is_file() else b"{}\n"
                    self._add_bytes(archive, manifest, config_bytes, "config.json")
                    archive.writestr(self.MANIFEST, json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
                with partial.open("r+b") as completed_archive:
                    completed_archive.flush()
                    os.fsync(completed_archive.fileno())
                valid, message = self.verify_archive(partial)
                if not valid:
                    raise RuntimeError(f"Backup validation failed: {message}")
                os.replace(partial, target)
                valid, message = self.verify_archive(target)
                if not valid:
                    target.unlink(missing_ok=True)
                    raise RuntimeError(f"Published backup validation failed: {message}")
                return target
            finally:
                partial.unlink(missing_ok=True)

    def _add_tree(self, archive, manifest, source: Path, archive_root: str) -> None:
        for path in sorted(source.rglob("*")):
            if any(part in {".staging", "__pycache__", ".cache"} for part in path.parts):
                continue
            if path.is_symlink():
                raise ValueError(f"Managed data contains a symbolic link: {path.relative_to(self.data_dir)}")
            if not path.is_file():
                continue
            resolved = path.resolve()
            # Backups may be placed below data; never ingest the destination tree.
            try:
                resolved.relative_to(self.backup_dir)
                continue
            except ValueError:
                pass
            relative = path.relative_to(source).as_posix()
            self._add_file(archive, manifest, path, f"{archive_root}/{relative}")

    @staticmethod
    def _add_file(archive, manifest, path: Path, name: str) -> None:
        digest = hashlib.sha256()
        size = 0
        with path.open("rb") as source, archive.open(name, "w") as target:
            while chunk := source.read(1024 * 1024):
                target.write(chunk)
                digest.update(chunk)
                size += len(chunk)
        manifest["files"][name] = {"size": size, "sha256": digest.hexdigest()}

    @staticmethod
    def _add_bytes(archive, manifest, data: bytes, name: str) -> None:
        archive.writestr(name, data)
        manifest["files"][name] = {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()}

    @staticmethod
    def _safe_member(name: str) -> bool:
        if not name or "\\" in name or name.startswith("/") or "\x00" in name:
            return False
        path = PurePosixPath(name)
        reserved = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
        return not path.is_absolute() and all(
            part not in ("", ".", "..")
            and not any(char in part for char in '<>:"|?*')
            and not part.endswith((".", " "))
            and part.split(".", 1)[0].upper() not in reserved
            for part in path.parts
        )

    def verify_archive(self, archive_path: str | Path) -> tuple[bool, str]:
        """Check archive paths, manifest hashes, SQLite integrity and referenced assets."""
        try:
            with zipfile.ZipFile(archive_path, "r") as archive:
                infos = archive.infolist()
                names = [entry.filename for entry in infos]
                if len(names) != len(set(names)):
                    return False, "The archive contains duplicate member names."
                for entry in infos:
                    if not self._safe_member(entry.filename.rstrip("/")):
                        return False, "The archive contains an unsafe member path."
                    mode = entry.external_attr >> 16
                    file_type = stat.S_IFMT(mode)
                    if stat.S_ISLNK(mode) or (file_type and file_type not in (stat.S_IFREG, stat.S_IFDIR)):
                        return False, "The archive contains an unsupported file type."
                    if entry.file_size > 2 * 1024 * 1024 * 1024:
                        return False, "The archive contains an unreasonably large member."
                    if entry.filename != self.MANIFEST and not entry.is_dir() and not self._allowed_member(entry.filename):
                        return False, f"The archive contains an unexpected member: {entry.filename}"
                if self.MANIFEST not in names or self.DB_MEMBER not in names or "config.json" not in names:
                    return False, "The archive is missing its manifest, database, or configuration."
                if archive.testzip() is not None:
                    return False, "The archive contains a corrupt member."
                manifest = json.loads(archive.read(self.MANIFEST))
                if not isinstance(manifest, dict) or manifest.get("format") != "bookledger-snapshot" or manifest.get("version") != 1 or not isinstance(manifest.get("files"), dict):
                    return False, "The archive manifest is malformed or unsupported."
                listed = set(manifest["files"])
                actual = {name for name in names if name != self.MANIFEST and not name.endswith("/")}
                if listed != actual:
                    return False, "The archive manifest does not match its contents."
                for name, expected in manifest["files"].items():
                    if not self._allowed_member(name) or not isinstance(expected, dict):
                        return False, "The archive manifest contains an unexpected file."
                    digest = hashlib.sha256()
                    size = 0
                    with archive.open(name, "r") as member:
                        while chunk := member.read(1024 * 1024):
                            digest.update(chunk)
                            size += len(chunk)
                    if expected.get("size") != size or expected.get("sha256") != digest.hexdigest():
                        return False, f"The archive member failed its checksum: {name}"
                with __import__("tempfile").TemporaryDirectory(prefix=".verify-", dir=self.backup_dir) as temp:
                    stage = Path(temp)
                    for name in actual:
                        destination = stage / PurePosixPath(name)
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        with archive.open(name, "r") as source, destination.open("wb") as target:
                            shutil.copyfileobj(source, target, length=1024 * 1024)
                    config = json.loads((stage / "config.json").read_text(encoding="utf-8"))
                    if not isinstance(config, dict):
                        return False, "The configuration snapshot must be a JSON object."
                    return self._validate_staged(stage)
        except (OSError, ValueError, KeyError, zipfile.BadZipFile, json.JSONDecodeError, sqlite3.DatabaseError) as exc:
            return False, f"The backup could not be validated ({type(exc).__name__})."

    @staticmethod
    def _allowed_member(name: str) -> bool:
        return name in ("config.json", BackupService.DB_MEMBER) or name.startswith(("data/photos/", "data/trash/", "data/assets/"))

    @staticmethod
    def _validate_staged(stage: Path) -> tuple[bool, str]:
        db_path = stage / BackupService.DB_MEMBER
        conn = sqlite3.connect(f"{db_path.as_uri()}?mode=ro", uri=True)
        try:
            result = conn.execute("PRAGMA integrity_check").fetchone()
            if not result or str(result[0]).lower() != "ok":
                return False, f"Database integrity check failed: {result[0] if result else 'no result'}"
            version = int(conn.execute("PRAGMA user_version").fetchone()[0])
            if version != SCHEMA_VERSION:
                return False, f"Unsupported database schema version: {version}"
            if conn.execute("PRAGMA foreign_key_check").fetchone():
                return False, "The database contains a foreign-key violation."
            required = {"copies", "book_records", "sales", "trash_entries", "storage_operations", "app_meta", "locations"}
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not required.issubset(tables):
                return False, "The database is missing required BookLedger tables."
            if conn.execute("SELECT 1 FROM storage_operations LIMIT 1").fetchone():
                return False, "The database has an unfinished managed-file operation. Resolve it before backing up or restoring."
            for photo_path, in conn.execute("SELECT photo_path FROM copies"):
                path = PurePosixPath(str(photo_path).replace("\\", "/"))
                if path.is_absolute() or ".." in path.parts or not path.parts or path.parts[0] not in ("photos", "trash"):
                    return False, "A copy refers to an unsafe managed-photo path."
                candidate = stage / "data" / path
                if not candidate.is_file():
                    return False, "A copy refers to a missing managed photo."
            return True, "Backup archive and library contents verified."
        finally:
            conn.close()

    def restore_backup(self, archive_path: str | Path) -> Path:
        """Replace the active library with a validated snapshot and retain recovery data."""
        valid, message = self.verify_archive(archive_path)
        if not valid:
            raise ValueError(f"Backup verification failed: {message}")
        with self.db.operation_guard():
            recovery = self.create_backup()
            self.latest_recovery_point = recovery
            work = self.data_dir.parent / f".bookledger-restore-{uuid.uuid4().hex}"
            work.mkdir(parents=True)
            journal = work / "restore.json"
            try:
                with zipfile.ZipFile(archive_path, "r") as archive:
                    for name in archive.namelist():
                        if name == self.MANIFEST or name.endswith("/"):
                            continue
                        target = work / "stage" / PurePosixPath(name)
                        target.parent.mkdir(parents=True, exist_ok=True)
                        with archive.open(name, "r") as source, target.open("wb") as destination:
                            shutil.copyfileobj(source, destination, length=1024 * 1024)
                stage = work / "stage"
                valid, message = self._validate_staged(stage)
                if not valid:
                    raise ValueError(f"Staged backup validation failed: {message}")
                items = self._component_paths()
                had_old = {key: target.exists() for key, target in items.items()}
                with journal.open("x", encoding="utf-8") as stream:
                    stream.write(json.dumps({"version": 1, "had_old": had_old}))
                    stream.flush()
                    os.fsync(stream.fileno())
                for key, target in items.items():
                    if key == "database":
                        staged = stage / self.DB_MEMBER
                    elif key == "config":
                        staged = stage / "config.json"
                    else:
                        staged = stage / "data" / key
                    if had_old[key]:
                        target.replace(work / f"old-{key}")
                    if staged.exists():
                        target.parent.mkdir(parents=True, exist_ok=True)
                        staged.replace(target)
                    elif key in ("photos", "trash", "assets"):
                        target.mkdir(parents=True, exist_ok=True)
                # Check the activated copy while the durable journal can still roll it back.
                check_root = work / "activated-check"
                check_root.mkdir()
                (check_root / "data").mkdir()
                shutil.copy2(self.db.path, check_root / self.DB_MEMBER)
                for name in ("photos", "trash", "assets"):
                    if (self.data_dir / name).exists():
                        shutil.copytree(self.data_dir / name, check_root / "data" / name)
                valid, message = self._validate_staged(check_root)
                if not valid:
                    raise RuntimeError(f"Activated library validation failed: {message}")
                journal.unlink()
                shutil.rmtree(work, ignore_errors=True)
                return recovery
            except Exception:
                self.recover_interrupted_restore(self.data_dir.parent)
                shutil.rmtree(work, ignore_errors=True)
                raise

    def _component_paths(self) -> dict[str, Path]:
        return {
            "database": self.db.path,
            "photos": self.data_dir / "photos",
            "trash": self.data_dir / "trash",
            "assets": self.data_dir / "assets",
            "config": self.config_path,
        }

    @classmethod
    def recover_interrupted_restore(cls, root: str | Path) -> tuple[str, ...]:
        """Roll back any interrupted component swap before normal app startup."""
        root = Path(root).resolve()
        data = root / "data"
        components = {"database": data / "bookledger.sqlite3", "photos": data / "photos", "trash": data / "trash", "assets": data / "assets", "config": root / "config.json"}
        recovered = []
        for work in root.glob(".bookledger-restore-*"):
            journal = work / "restore.json"
            if not journal.is_file():
                continue
            try:
                state = json.loads(journal.read_text(encoding="utf-8"))
                had_old = state.get("had_old")
                if (
                    state.get("version") != 1
                    or not isinstance(had_old, dict)
                    or set(had_old) != set(cls.COMPONENTS)
                    or any(type(value) is not bool for value in had_old.values())
                ):
                    raise ValueError("Invalid restore recovery journal")
                for key in reversed(cls.COMPONENTS):
                    target = components[key]
                    old = work / f"old-{key}"
                    if had_old.get(key):
                        if old.exists():
                            cls._remove_component(target)
                            target.parent.mkdir(parents=True, exist_ok=True)
                            old.replace(target)
                        elif not target.exists():
                            raise FileNotFoundError(f"Previous {key} component is missing")
                    elif target.exists():
                        # A component absent before restore may have been installed by it.
                        if (work / "stage").exists():
                            staged = work / "stage" / ("config.json" if key == "config" else cls.DB_MEMBER if key == "database" else f"data/{key}")
                            if not staged.exists():
                                cls._remove_component(target)
                recovered.append(work.name)
                shutil.rmtree(work, ignore_errors=True)
            except Exception as exc:
                raise RuntimeError(f"Interrupted restore recovery failed in {work.name} ({type(exc).__name__}).") from exc
        return tuple(recovered)

    @staticmethod
    def _remove_component(path: Path) -> None:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink(missing_ok=True)
