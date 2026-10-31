from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import stat
import tempfile
import uuid
import zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath
import re

from bookledger.db.database import SCHEMA_VERSION, Database


class BackupService:
    """Complete portable library snapshots and recoverable snapshot replacement."""

    MANIFEST = "manifest.json"
    DB_MEMBER = "data/bookledger.sqlite3"
    COMPONENTS = ("database", "photos", "trash", "assets", "config", "poster_backgrounds", "application_assets", "posters")
    POSTER_BACKGROUND_PATTERN = re.compile(r"^template_background_\d+\.(?:png|jpe?g|webp)$", re.IGNORECASE)
    POSTER_OUTPUT_PATTERN = re.compile(r"^BL-\d{6,}\.png$", re.IGNORECASE)

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
                    for directory in ("photos", "trash", "assets", "poster_backgrounds"):
                        source = self.data_dir / directory
                        if source.exists():
                            self._add_tree(archive, manifest, source, f"data/{directory}")
                    app_assets = self.data_dir.parent / "assets"
                    if app_assets.is_dir():
                        for path in sorted(app_assets.iterdir()):
                            if path.is_file() and not path.is_symlink() and self.POSTER_BACKGROUND_PATTERN.fullmatch(path.name):
                                self._add_file(archive, manifest, path, f"application_assets/{path.name}")
                    included_posters = set()
                    for posters in (self.data_dir / "posters", self.data_dir.parent / "posters"):
                        if posters.is_dir():
                            for path in sorted(posters.iterdir()):
                                if path.is_file() and not path.is_symlink() and self.POSTER_OUTPUT_PATTERN.fullmatch(path.name) and path.name not in included_posters:
                                    self._add_file(archive, manifest, path, f"posters/{path.name}")
                                    included_posters.add(path.name)
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
        if name in ("config.json", BackupService.DB_MEMBER):
            return True
        parts = PurePosixPath(name).parts
        if len(parts) == 2 and parts[0] == "application_assets":
            return bool(BackupService.POSTER_BACKGROUND_PATTERN.fullmatch(parts[1]))
        if len(parts) == 2 and parts[0] == "posters":
            return bool(BackupService.POSTER_OUTPUT_PATTERN.fullmatch(parts[1]))
        return name.startswith(("data/photos/", "data/trash/", "data/assets/", "data/poster_backgrounds/"))

    @staticmethod
    def _validate_staged(stage: Path) -> tuple[bool, str]:
        db_path = stage / BackupService.DB_MEMBER
        try:
            preflight = sqlite3.connect(f"{db_path.as_uri()}?mode=ro", uri=True)
            try:
                version = int(preflight.execute("PRAGMA user_version").fetchone()[0])
            finally:
                preflight.close()
            if 1 <= version < SCHEMA_VERSION:
                Database(db_path)  # Apply the project's sequential migrations in the isolated stage.
            elif version != SCHEMA_VERSION:
                return False, f"Unsupported database schema version: {version}"
        except Exception as exc:
            return False, f"Database migration failed: {type(exc).__name__}."
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
            required = {"copies", "book_records", "sales", "trash_entries", "storage_operations", "app_meta", "locations", "poster_templates"}
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
            for background_ref, in conn.execute("SELECT background_ref FROM poster_templates"):
                relative = PurePosixPath(str(background_ref))
                if relative.is_absolute() or ".." in relative.parts or "\\" in str(background_ref):
                    return False, "A poster template refers to an unsafe background path."
                if relative.parts[:1] == ("assets",) and len(relative.parts) == 2:
                    candidate = stage / "data" / "assets" / relative.name
                    if not candidate.is_file():
                        candidate = stage / "application_assets" / relative.name
                elif relative.parts[:2] == ("data", "poster_backgrounds") and len(relative.parts) == 3:
                    candidate = stage / "data" / "poster_backgrounds" / relative.name
                else:
                    return False, "A poster template refers to a background outside managed poster storage."
                if not candidate.is_file():
                    return False, "A poster template refers to a missing background."
            return True, "Backup archive and library contents verified."
        finally:
            conn.close()

    @classmethod
    def _promote_legacy_backgrounds(cls, stage: Path) -> None:
        """Copy old root/fallback backgrounds into canonical data/assets on restore."""
        assets = stage / "data" / "assets"
        assets.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(stage / cls.DB_MEMBER)
        try:
            refs = [str(row[0]) for row in conn.execute("SELECT background_ref FROM poster_templates")]
            changes = {}
            for reference in refs:
                relative = PurePosixPath(reference)
                if relative.is_absolute() or ".." in relative.parts or "\\" in reference:
                    continue
                if relative.parts[:1] == ("assets",) and len(relative.parts) == 2:
                    old_name = relative.name
                    if (assets / old_name).is_file():
                        continue
                    source = stage / "application_assets" / old_name
                    new_name = old_name
                elif relative.parts[:2] == ("data", "poster_backgrounds") and len(relative.parts) == 3:
                    old_name = relative.name
                    source = stage / "data" / "poster_backgrounds" / old_name
                    new_name = old_name
                else:
                    continue
                if not source.is_file() or source.is_symlink():
                    continue
                destination = assets / new_name
                if destination.exists() and destination.read_bytes() != source.read_bytes():
                    index = 1
                    suffix = source.suffix
                    while (assets / f"template_background_{index}{suffix}").exists():
                        index += 1
                    new_name = f"template_background_{index}{suffix}"
                    destination = assets / new_name
                if not destination.exists():
                    shutil.copy2(source, destination)
                if reference.startswith("data/poster_backgrounds/") or new_name != old_name:
                    changes[reference] = f"assets/{new_name}"
            for old_reference, new_reference in changes.items():
                conn.execute(
                    "UPDATE poster_templates SET background_ref=? WHERE background_ref=?",
                    (new_reference, old_reference),
                )
            conn.commit()
        finally:
            conn.close()
        for directory in (stage / "application_assets", stage / "data" / "poster_backgrounds"):
            if not directory.is_dir():
                continue
            for source in directory.iterdir():
                if source.is_symlink() or not source.is_file() or not cls.POSTER_BACKGROUND_PATTERN.fullmatch(source.name):
                    continue
                destination = assets / source.name
                if destination.exists() and destination.read_bytes() != source.read_bytes():
                    index = 1
                    while (assets / f"template_background_{index}{source.suffix}").exists():
                        index += 1
                    destination = assets / f"template_background_{index}{source.suffix}"
                if not destination.exists():
                    shutil.copy2(source, destination)
        app_assets = stage / "application_assets"
        if app_assets.is_dir():
            shutil.rmtree(app_assets)
        legacy_fallback = stage / "data" / "poster_backgrounds"
        if legacy_fallback.is_dir():
            for path in legacy_fallback.iterdir():
                if path.is_file() and not path.is_symlink() and cls.POSTER_BACKGROUND_PATTERN.fullmatch(path.name):
                    path.unlink()
            try:
                legacy_fallback.rmdir()
            except OSError:
                pass

    @staticmethod
    def _preserve_unmanaged_assets(current: Path, staged: Path) -> None:
        """Carry user files through restore while replacing app-managed logos/backgrounds."""
        if current.is_symlink():
            raise ValueError("Refusing to restore through a linked managed assets directory.")
        staged.mkdir(parents=True, exist_ok=True)
        managed = re.compile(
            r"^(?:template_background_\d+\.(?:png|jpe?g|webp)|shop-logo-[0-9a-f]{20}\.png)$",
            re.IGNORECASE,
        )
        if not current.is_dir():
            return
        for path in current.rglob("*"):
            if path.is_symlink():
                raise ValueError("Managed assets contain a symbolic link; restore was stopped to preserve file safety.")
            if not path.is_file() or managed.fullmatch(path.name):
                continue
            relative = path.relative_to(current)
            destination = staged / relative
            if not destination.exists():
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, destination)

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
                # Promote poster backgrounds from older backup layouts into the
                # canonical mutable data/assets folder before activation.
                self._promote_legacy_backgrounds(stage)
                valid, message = self._validate_staged(stage)
                if not valid:
                    raise ValueError(f"Normalized backup validation failed: {message}")
                self._preserve_unmanaged_assets(self.data_dir / "assets", stage / "data" / "assets")
                skipped_components = {"application_assets"}
                for key, target, pattern in (
                    ("posters", self.data_dir / "posters", self.POSTER_OUTPUT_PATTERN),
                ):
                    if key in skipped_components:
                        continue
                    if target.exists() and not target.is_dir():
                        raise ValueError(f"Refusing to replace a non-directory poster component: {target.name}")
                    staged_subset = stage / key
                    merged = work / f"merged-{key}"
                    if target.is_symlink():
                        raise ValueError(f"Refusing to restore through a linked managed directory: {target.name}")
                    if target.is_dir():
                        shutil.copytree(target, merged, symlinks=True)
                    else:
                        merged.mkdir(parents=True)
                    for existing in merged.iterdir():
                        if pattern.fullmatch(existing.name):
                            if existing.is_dir():
                                shutil.rmtree(existing)
                            else:
                                existing.unlink()
                    if staged_subset.is_dir():
                        for incoming in staged_subset.iterdir():
                            shutil.copy2(incoming, merged / incoming.name)
                    if staged_subset.exists():
                        shutil.rmtree(staged_subset)
                    shutil.copytree(merged, staged_subset)
                items = self._component_paths()
                had_old = {key: (target.exists() or key in skipped_components) for key, target in items.items()}
                with journal.open("x", encoding="utf-8") as stream:
                    stream.write(json.dumps({"version": 2, "had_old": had_old, "skipped": sorted(skipped_components)}))
                    stream.flush()
                    os.fsync(stream.fileno())
                for key, target in items.items():
                    if key in skipped_components:
                        continue
                    if key == "database":
                        staged = stage / self.DB_MEMBER
                    elif key == "config":
                        staged = stage / "config.json"
                    elif key == "posters":
                        staged = stage / "posters"
                    else:
                        staged = stage / "data" / key
                    if had_old[key]:
                        target.replace(work / f"old-{key}")
                    if staged.exists():
                        target.parent.mkdir(parents=True, exist_ok=True)
                        staged.replace(target)
                    elif key in ("photos", "trash", "assets", "poster_backgrounds", "posters"):
                        target.mkdir(parents=True, exist_ok=True)
                # Check the activated copy while the durable journal can still roll it back.
                check_root = work / "activated-check"
                check_root.mkdir()
                (check_root / "data").mkdir()
                shutil.copy2(self.db.path, check_root / self.DB_MEMBER)
                for name in ("photos", "trash", "assets", "poster_backgrounds"):
                    if (self.data_dir / name).exists():
                        shutil.copytree(self.data_dir / name, check_root / "data" / name)
                for name in ("posters",):
                    source = self.data_dir / "posters"
                    if source.is_dir():
                        shutil.copytree(source, check_root / name)
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
            "poster_backgrounds": self.data_dir / "poster_backgrounds",
            "config": self.config_path,
            "application_assets": self.data_dir.parent / "assets",
            "posters": self.data_dir / "posters",
        }

    @classmethod
    def recover_interrupted_restore(cls, root: str | Path) -> tuple[str, ...]:
        """Roll back any interrupted component swap before normal app startup."""
        root = Path(root).resolve()
        data = root / "data"
        components = {"database": data / "bookledger.sqlite3", "photos": data / "photos", "trash": data / "trash", "assets": data / "assets", "poster_backgrounds": data / "poster_backgrounds", "config": root / "config.json", "application_assets": root / "assets", "posters": data / "posters"}
        recovered = []
        for work in root.glob(".bookledger-restore-*"):
            journal = work / "restore.json"
            if not journal.is_file():
                continue
            try:
                state = json.loads(journal.read_text(encoding="utf-8"))
                had_old = state.get("had_old")
                skipped = state.get("skipped", [])
                legacy_components = {"database", "photos", "trash", "assets", "config"}
                if (
                    state.get("version") not in (1, 2)
                    or not isinstance(had_old, dict)
                    or set(had_old) not in (set(cls.COMPONENTS), legacy_components)
                    or not isinstance(skipped, list)
                    or any(key not in cls.COMPONENTS for key in skipped)
                    or any(type(value) is not bool for value in had_old.values())
                ):
                    raise ValueError("Invalid restore recovery journal")
                had_old = {key: had_old.get(key, False) for key in cls.COMPONENTS}
                for key in reversed(cls.COMPONENTS):
                    if key in skipped:
                        continue
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
                        # The component did not exist before activation, so remove
                        # any directory or file installed from the selected snapshot.
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
