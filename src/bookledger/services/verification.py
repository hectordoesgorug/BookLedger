from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from bookledger.db.database import Database


@dataclass(frozen=True)
class VerificationReport:
    ok: bool
    message: str
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


class VerificationService:
    """Read-only database, photo-tree, and storage-operation consistency checks."""

    def __init__(self, db: Database, data_dir: str | Path):
        self.db = db
        self.data_dir = Path(data_dir).resolve()

    def verify(self) -> VerificationReport:
        errors: list[str] = []
        warnings: list[str] = []
        referenced_active: set[Path] = set()
        referenced_trash: set[Path] = set()
        with self.db.connect() as conn:
            integrity = conn.execute("PRAGMA integrity_check").fetchall()
            if not integrity or any(str(row[0]).lower() != "ok" for row in integrity):
                errors.extend(f"SQLite integrity: {row[0]}" for row in integrity)
            for table, rowid, parent, fkid in conn.execute("PRAGMA foreign_key_check"):
                errors.append(f"Foreign-key violation: {table} row {rowid} references {parent} (constraint {fkid}).")
            for row in conn.execute("SELECT c.id,c.book_id FROM copies c LEFT JOIN book_records b ON b.id=c.book_id WHERE b.id IS NULL"):
                errors.append(f"Copy ID {row['id']} references missing bibliographic record {row['book_id']}.")
            for row in conn.execute("SELECT s.id,s.copy_id FROM sales s LEFT JOIN copies c ON c.id=s.copy_id WHERE c.id IS NULL"):
                errors.append(f"Sale ID {row['id']} references missing Copy ID {row['copy_id']}.")
            for row in conn.execute("SELECT copy_code,GROUP_CONCAT(id) ids FROM copies WHERE copy_code IS NOT NULL AND trim(copy_code)<>'' GROUP BY copy_code HAVING COUNT(*)>1"):
                errors.append(f"Duplicate Copy Code {row['copy_code']!r} is used by Copy IDs {row['ids']}.")
            for row in conn.execute("SELECT id,copy_code,photo_path FROM copies ORDER BY id"):
                copy_id, code, photo = int(row["id"]), row["copy_code"], row["photo_path"]
                if copy_id <= 0 or not code:
                    errors.append(f"Copy ID {copy_id} has an invalid identity or empty copy code.")
                candidate = self._resolve(photo)
                if candidate is None:
                    errors.append(f"Copy ID {copy_id} has an unsafe photo path: {photo!r}.")
                    continue
                is_trash = bool(conn.execute("SELECT 1 FROM trash_entries WHERE copy_id=?", (copy_id,)).fetchone())
                if is_trash:
                    referenced_trash.add(candidate)
                    expected = (self.data_dir / "trash" / f"{copy_id}.jpg").resolve()
                    if candidate != expected:
                        errors.append(f"Trashed Copy ID {copy_id} has non-canonical path {photo!r}.")
                else:
                    referenced_active.add(candidate)
                    expected = (self.data_dir / "photos" / f"{copy_id}.jpg").resolve()
                    if candidate != expected:
                        errors.append(f"Active Copy ID {copy_id} has non-canonical path {photo!r}.")
                if not candidate.is_file():
                    errors.append(f"Copy ID {copy_id} photo is missing: {candidate}")
            shared = conn.execute("SELECT photo_path,GROUP_CONCAT(id) ids,COUNT(*) n FROM copies GROUP BY photo_path HAVING COUNT(*)>1").fetchall()
            for row in shared:
                warnings.append(f"Shared photo reference ({row['ids']}): {row['photo_path']}")
            trash_without_copy = conn.execute("SELECT t.copy_id FROM trash_entries t LEFT JOIN copies c ON c.id=t.copy_id WHERE c.id IS NULL").fetchall()
            errors.extend(f"Trash metadata references missing Copy ID {r[0]}." for r in trash_without_copy)
            for row in conn.execute("SELECT copy_id,original_status FROM trash_entries WHERE original_status NOT IN ('Available','Not for Sale','Listed','Sold')"):
                errors.append(f"Trash metadata for Copy ID {row['copy_id']} has invalid original status {row['original_status']!r}.")
            operations = conn.execute("SELECT id,operation,copy_id,source_path,target_path,state FROM storage_operations ORDER BY id").fetchall()
            for operation in operations:
                errors.append(f"Unfinished storage operation {operation['id']} ({operation['operation']}) for Copy ID {operation['copy_id']}: {operation['state']}.")
        for folder, expected in ((self.data_dir / "photos", referenced_active), (self.data_dir / "trash", referenced_trash)):
            if not folder.exists():
                continue
            for item in folder.rglob("*"):
                if not item.is_file():
                    continue
                if ".staging" in item.parts:
                    errors.append(f"Abandoned staging file: {item}")
                elif item.resolve() not in expected:
                    warnings.append(f"Unreferenced file: {item}")
        if errors:
            details = "\n".join(f"• {item}" for item in errors + warnings)
            return VerificationReport(False, f"Verification found {len(errors)} error(s) and {len(warnings)} warning(s):\n{details}", tuple(errors), tuple(warnings))
        if warnings:
            details = "\n".join(f"• {item}" for item in warnings)
            return VerificationReport(True, f"Database and photo checks passed with {len(warnings)} warning(s):\n{details}", (), tuple(warnings))
        return VerificationReport(True, "Database, relationships, and managed photo files passed verification.")

    def _resolve(self, relative: str) -> Path | None:
        candidate = (self.data_dir / str(relative)).resolve()
        try:
            candidate.relative_to(self.data_dir)
        except ValueError:
            return None
        return candidate
