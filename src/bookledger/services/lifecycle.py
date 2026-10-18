from __future__ import annotations

import shutil
from pathlib import Path

from bookledger.db.database import Database
from bookledger.services.photos import PhotoService


class CopyLifecycleService:
    """Coordinate copy trash operations with recoverable same-volume file moves."""

    def __init__(self, db: Database, data_dir: str | Path):
        self.db = db
        self._data_path = Path(data_dir).absolute()
        self.data_dir = self._data_path.resolve()
        self.photos = PhotoService(self.data_dir / "photos", self.data_dir / "trash")

    def _safe(self, relative: str) -> Path:
        candidate = (self.data_dir / relative).resolve()
        candidate.relative_to(self.data_dir)
        return candidate

    def trash_copy(self, copy_id: int) -> None:
        with self.db.connect() as conn:
            row = conn.execute("SELECT photo_path,status FROM copies WHERE id=?", (copy_id,)).fetchone()
            if not row:
                raise KeyError(f"Copy {copy_id} was not found")
            if conn.execute("SELECT 1 FROM trash_entries WHERE copy_id=?", (copy_id,)).fetchone():
                return
            source = self._safe(row["photo_path"])
            target = self.data_dir / "trash" / f"{copy_id}.jpg"
            if not source.is_file():
                raise FileNotFoundError(f"Copy {copy_id} photo is missing: {source}")
            if target.exists():
                raise FileExistsError(f"Trash photo already exists for Copy ID {copy_id}: {target}")
            conn.execute("INSERT INTO storage_operations(operation,copy_id,source_path,target_path,state) VALUES('trash',?,?,?,'prepared')",
                         (copy_id, source.relative_to(self.data_dir).as_posix(), target.relative_to(self.data_dir).as_posix()))
        try:
            source.replace(target)
            with self.db.connect() as conn:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute("INSERT INTO trash_entries(copy_id,original_status) VALUES(?,?)", (copy_id, row["status"]))
                conn.execute("UPDATE copies SET photo_path=? WHERE id=?", (f"trash/{copy_id}.jpg", copy_id))
                conn.execute("DELETE FROM storage_operations WHERE operation='trash' AND copy_id=?", (copy_id,))
        except Exception:
            try:
                if target.exists() and not source.exists():
                    target.replace(source)
                with self.db.connect() as conn:
                    conn.execute("DELETE FROM storage_operations WHERE operation='trash' AND copy_id=?", (copy_id,))
            except OSError:
                pass
            raise

    def restore_latest(self) -> int | None:
        with self.db.connect() as conn:
            row = conn.execute("SELECT t.id,t.copy_id,c.photo_path FROM trash_entries t JOIN copies c ON c.id=t.copy_id ORDER BY t.id DESC LIMIT 1").fetchone()
            if not row:
                return None
            copy_id = int(row["copy_id"])
            source = self._safe(row["photo_path"])
            target = self.data_dir / "photos" / f"{copy_id}.jpg"
            if not source.is_file():
                raise FileNotFoundError(f"Trashed photo for Copy ID {copy_id} is missing: {source}")
            if target.exists():
                raise FileExistsError(f"Active photo already exists for Copy ID {copy_id}: {target}")
            conn.execute("INSERT INTO storage_operations(operation,copy_id,source_path,target_path,state) VALUES('restore',?,?,?,'prepared')",
                         (copy_id, source.relative_to(self.data_dir).as_posix(), target.relative_to(self.data_dir).as_posix()))
        try:
            source.replace(target)
            with self.db.connect() as conn:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute("UPDATE copies SET photo_path=? WHERE id=?", (f"photos/{copy_id}.jpg", copy_id))
                conn.execute("DELETE FROM trash_entries WHERE copy_id=?", (copy_id,))
                conn.execute("DELETE FROM storage_operations WHERE operation='restore' AND copy_id=?", (copy_id,))
            return copy_id
        except Exception:
            try:
                if target.exists() and not source.exists():
                    target.replace(source)
                with self.db.connect() as conn:
                    conn.execute("DELETE FROM storage_operations WHERE operation='restore' AND copy_id=?", (copy_id,))
            except OSError:
                pass
            raise

    def trash_count(self) -> int:
        with self.db.connect() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM trash_entries").fetchone()[0])

    def retry_pending_operations(self) -> tuple[str, ...]:
        """Explicitly resume durable filesystem work left by an interrupted operation."""
        with self.db.connect() as conn:
            operations = conn.execute("SELECT * FROM storage_operations ORDER BY id").fetchall()
        failures: list[str] = []
        for op in operations:
            try:
                source = self._safe(op["source_path"]) if op["source_path"] else None
                target = self._safe(op["target_path"]) if op["target_path"] else None
                copy_id = op["copy_id"]
                if op["operation"] == "install":
                    if target and target.is_file():
                        if source and source.exists():
                            raise FileExistsError("Staged and canonical photos both exist; manual review is required")
                        with self.db.connect() as conn:
                            row = conn.execute("SELECT photo_path FROM copies WHERE id=?", (copy_id,)).fetchone()
                        if not row or self._safe(row["photo_path"]) != target:
                            raise ValueError("Canonical photo does not match the pending copy record")
                    elif source and source.is_file() and target:
                        self.photos.install(int(copy_id), source)
                    else:
                        raise FileNotFoundError("Neither staged nor canonical photo exists")
                    self._finish_operation(op["id"])
                elif op["operation"] == "replace":
                    if source and source.is_file() and copy_id is not None:
                        self.photos.replace(int(copy_id), source)
                    elif not (target and target.is_file()):
                        raise FileNotFoundError("Replacement photo and canonical photo are both missing")
                    self._finish_operation(op["id"])
                elif op["operation"] == "migrate":
                    if source and source.is_file() and target and not target.exists():
                        target.parent.mkdir(parents=True, exist_ok=True)
                        source.replace(target)
                    elif source and source.exists() and target and target.exists():
                        raise FileExistsError("Both staged and canonical migration photos exist")
                    elif not (target and target.is_file()):
                        raise FileNotFoundError("Staged and canonical migration photos are both missing")
                    with self.db.connect() as conn:
                        conn.execute("UPDATE copies SET photo_path=? WHERE id=?", (op["target_path"], copy_id))
                        conn.execute("DELETE FROM storage_operations WHERE id=?", (op["id"],))
                elif op["operation"] in {"trash", "restore"}:
                    if not source or not target:
                        raise ValueError("Operation paths are incomplete")
                    if source.exists() and target.exists():
                        raise FileExistsError("Both source and target photos exist; manual review is required")
                    if source.exists():
                        source.replace(target)
                    elif not target.exists():
                        raise FileNotFoundError("Both operation photo paths are missing")
                    with self.db.connect() as conn:
                        conn.execute("BEGIN IMMEDIATE")
                        if op["operation"] == "trash":
                            status = conn.execute("SELECT status FROM copies WHERE id=?", (copy_id,)).fetchone()
                            if status:
                                conn.execute("INSERT OR IGNORE INTO trash_entries(copy_id,original_status) VALUES(?,?)", (copy_id, status[0]))
                                conn.execute("UPDATE copies SET photo_path=? WHERE id=?", (op["target_path"], copy_id))
                        else:
                            conn.execute("UPDATE copies SET photo_path=? WHERE id=?", (op["target_path"], copy_id))
                            conn.execute("DELETE FROM trash_entries WHERE copy_id=?", (copy_id,))
                        conn.execute("DELETE FROM storage_operations WHERE id=?", (op["id"],))
                elif op["operation"] == "cleanup":
                    with self.db.connect() as conn:
                        refs = conn.execute("SELECT COUNT(*) FROM copies WHERE photo_path=?", (op["source_path"],)).fetchone()[0]
                    if refs:
                        self._finish_operation(op["id"])
                        continue
                    if source:
                        source.unlink(missing_ok=True)
                    self._finish_operation(op["id"])
                else:
                    raise ValueError(f"Unknown operation type {op['operation']!r}")
            except Exception as exc:
                failures.append(f"Operation {op['id']} ({op['operation']}, Copy ID {op['copy_id']}): {exc}")
        return tuple(failures)

    def _finish_operation(self, operation_id: int) -> None:
        with self.db.connect() as conn:
            conn.execute("DELETE FROM storage_operations WHERE id=?", (operation_id,))

    def clear_trash(self) -> int:
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            rows = conn.execute("SELECT c.id,c.book_id,c.photo_path FROM copies c JOIN trash_entries t ON t.copy_id=c.id ORDER BY t.id").fetchall()
            deleting_ids = [int(row["id"]) for row in rows]
            placeholders = ",".join("?" for _ in deleting_ids)
            cleanup_paths: set[str] = set()
            for row in rows:
                photo_path = str(row["photo_path"])
                # Only copies that survive this clear prevent photo cleanup.
                if photo_path not in cleanup_paths:
                    refs = conn.execute(
                        f"SELECT COUNT(*) FROM copies WHERE photo_path=? AND id NOT IN ({placeholders})",
                        (photo_path, *deleting_ids),
                    ).fetchone()[0] if deleting_ids else 0
                else:
                    refs = 0
                if not refs and photo_path not in cleanup_paths:
                    conn.execute("INSERT INTO storage_operations(operation,copy_id,source_path,state) VALUES('cleanup',?,?,'pending')",
                                 (row["id"], photo_path))
                    cleanup_paths.add(photo_path)
                conn.execute("DELETE FROM sales WHERE copy_id=?", (row["id"],))
                conn.execute("DELETE FROM trash_entries WHERE copy_id=?", (row["id"],))
                conn.execute("DELETE FROM copies WHERE id=?", (row["id"],))
                conn.execute("DELETE FROM book_records WHERE id=? AND NOT EXISTS (SELECT 1 FROM copies WHERE book_id=?)",
                             (row["book_id"], row["book_id"]))
        failures = []
        for row in rows:
            with self.db.connect() as conn:
                op = conn.execute("SELECT id,source_path FROM storage_operations WHERE operation='cleanup' AND copy_id=?", (row["id"],)).fetchone()
                if not op:
                    continue
                refs = conn.execute("SELECT COUNT(*) FROM copies WHERE photo_path=?", (op["source_path"],)).fetchone()[0]
            if refs:
                with self.db.connect() as conn:
                    conn.execute("DELETE FROM storage_operations WHERE id=?", (op["id"],))
                continue
            try:
                self._safe(op["source_path"]).unlink(missing_ok=True)
                with self.db.connect() as conn:
                    conn.execute("DELETE FROM storage_operations WHERE id=?", (op["id"],))
            except OSError as exc:
                failures.append(f"Copy {row['id']}: {exc}")
        if failures:
            raise RuntimeError("Trash records were cleared, but photo cleanup needs retry: " + "; ".join(failures))
        return len(rows)

    def purge(self) -> None:
        """Remove managed data only; never target the root backups directory."""
        root = self.data_dir.resolve()
        expected_root = self._data_path.parent.resolve() / "data"
        if (
            self._data_path.is_symlink()
            or self._data_path.name.casefold() != "data"
            or root != expected_root
            or self.db.path.parent.resolve() != root
        ):
            raise RuntimeError(f"Refusing to purge unexpected managed directory: {root}")
        for child in root.iterdir():
            resolved = child.resolve()
            resolved.relative_to(root)
            if child.is_dir() and not child.is_symlink():
                shutil.rmtree(child)
            else:
                child.unlink()
        self.db.path.parent.mkdir(parents=True, exist_ok=True)
        # Reinitialization happens through the app after the existing DB is removed.
