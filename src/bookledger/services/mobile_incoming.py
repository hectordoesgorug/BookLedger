from __future__ import annotations

import json
import os
import sqlite3
import threading
import tempfile
import uuid
from email import policy
from email.parser import BytesParser
from pathlib import Path
from typing import Any

from PIL import Image

from bookledger.db.database import Database
from bookledger.services.isbn import isbn_check, normalize_isbn

MAX_PHOTO_BYTES = 25 * 1024 * 1024
MAX_METADATA_BYTES = 8 * 1024
MAX_BATCH_SIZE = 20


class IncomingCaptureError(ValueError):
    def __init__(self, code: str, status: int = 400):
        super().__init__(code)
        self.code = code
        self.status = status


class MobileIncomingStore:
    """Durably stage authenticated mobile captures outside ordinary inventory."""

    def __init__(self, db: Database, data_dir: str | Path):
        self.db = db
        self.data_dir = Path(data_dir).resolve()
        self.root = self.data_dir / "incoming"
        self.root.mkdir(parents=True, exist_ok=True)
        self._receive_lock = threading.RLock()

    @staticmethod
    def _uuid(value: Any, field: str) -> str:
        if not isinstance(value, str):
            raise IncomingCaptureError(f"invalid_{field}")
        try:
            return str(uuid.UUID(value))
        except (ValueError, AttributeError) as exc:
            raise IncomingCaptureError(f"invalid_{field}") from exc

    def begin_batch(self, batch_id: Any, expected_count: Any) -> dict:
        batch_id = self._uuid(batch_id, "batch_id")
        if type(expected_count) is not int or not 1 <= expected_count <= MAX_BATCH_SIZE:
            raise IncomingCaptureError("invalid_batch_size")
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT expected_count,state,cataloged_at FROM mobile_incoming_batches WHERE batch_uuid=?",
                (batch_id,),
            ).fetchone()
            if row:
                if row["expected_count"] != expected_count:
                    raise IncomingCaptureError("batch_conflict", 409)
                return {"ok": True, "batch_id": batch_id, "expected_count": expected_count}
            conn.execute(
                "INSERT INTO mobile_incoming_batches(batch_uuid,expected_count,state) VALUES(?,?,'receiving')",
                (batch_id, expected_count),
            )
        return {"ok": True, "batch_id": batch_id, "expected_count": expected_count}

    @staticmethod
    def _multipart(content_type: str, body: bytes) -> tuple[dict, bytes]:
        if not content_type.lower().startswith("multipart/form-data;"):
            raise IncomingCaptureError("multipart_required", 415)
        envelope = (
            f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("ascii")
            + body
        )
        message = BytesParser(policy=policy.default).parsebytes(envelope)
        if not message.is_multipart():
            raise IncomingCaptureError("invalid_multipart")
        fields: dict[str, bytes] = {}
        for part in message.iter_parts():
            name = part.get_param("name", header="content-disposition")
            if name not in {"metadata", "photo"} or name in fields:
                raise IncomingCaptureError("invalid_multipart")
            data = part.get_payload(decode=True)
            if not isinstance(data, bytes):
                raise IncomingCaptureError("invalid_multipart")
            fields[name] = data
        if set(fields) != {"metadata", "photo"}:
            raise IncomingCaptureError("invalid_multipart")
        if len(fields["metadata"]) > MAX_METADATA_BYTES:
            raise IncomingCaptureError("metadata_too_large", 413)
        try:
            metadata = json.loads(fields["metadata"])
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise IncomingCaptureError("invalid_metadata") from exc
        if not isinstance(metadata, dict):
            raise IncomingCaptureError("invalid_metadata")
        return metadata, fields["photo"]

    def receive_capture(self, batch_id: Any, capture_id: Any, content_type: str, body: bytes) -> dict:
        with self._receive_lock:
            return self._receive_capture(batch_id, capture_id, content_type, body)

    def _receive_capture(self, batch_id: Any, capture_id: Any, content_type: str, body: bytes) -> dict:
        batch_id = self._uuid(batch_id, "batch_id")
        capture_id = self._uuid(capture_id, "capture_id")
        metadata, photo = self._multipart(content_type, body)
        if len(photo) == 0 or len(photo) > MAX_PHOTO_BYTES:
            raise IncomingCaptureError("invalid_photo_size", 413)
        if not photo.startswith(b"\xff\xd8\xff"):
            raise IncomingCaptureError("jpeg_required", 415)
        try:
            sequence = metadata["sequence"]
            if type(sequence) is not int:
                raise ValueError
            isbn = metadata.get("isbn")
            if isbn is not None:
                isbn = normalize_isbn(isbn)
                if isbn is None or not isbn_check(isbn)[0]:
                    raise IncomingCaptureError("invalid_isbn")
            captured_at = metadata["captured_at"]
            if not isinstance(captured_at, str) or len(captured_at) > 64:
                raise ValueError
            from datetime import datetime
            datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
        except IncomingCaptureError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise IncomingCaptureError("invalid_metadata") from exc

        with self.db.connect() as conn:
            batch = conn.execute(
                "SELECT expected_count,state,cataloged_at FROM mobile_incoming_batches WHERE batch_uuid=?",
                (batch_id,),
            ).fetchone()
            if not batch:
                raise IncomingCaptureError("batch_not_found", 404)
            if not 1 <= sequence <= batch["expected_count"]:
                raise IncomingCaptureError("invalid_sequence")
            existing = conn.execute(
                "SELECT batch_uuid,sequence,isbn,captured_at FROM mobile_incoming_captures WHERE capture_uuid=?",
                (capture_id,),
            ).fetchone()
            if existing:
                if (existing["batch_uuid"], existing["sequence"], existing["isbn"], existing["captured_at"]) != (
                    batch_id, sequence, isbn, captured_at
                ):
                    raise IncomingCaptureError("capture_conflict", 409)
                photo_path = self._photo_path(batch_id, capture_id)
                if photo_path.is_file() or conn.execute(
                    "SELECT 1 FROM copies WHERE copy_uuid=?", (capture_id,)
                ).fetchone():
                    count = conn.execute(
                        "SELECT COUNT(*) FROM mobile_incoming_captures WHERE batch_uuid=?", (batch_id,)
                    ).fetchone()[0]
                    if batch["state"] == "receiving" and count == batch["expected_count"]:
                        conn.execute(
                            "UPDATE mobile_incoming_batches SET state='ready',updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE batch_uuid=?",
                            (batch_id,),
                        )
                    return {
                        "ok": True,
                        "capture_id": capture_id,
                        "received": True,
                        "duplicate": True,
                        "ready": batch["cataloged_at"] is None and count == batch["expected_count"],
                    }
            elif batch["state"] != "receiving":
                raise IncomingCaptureError("batch_not_receiving", 409)

        photo_path = self._photo_path(batch_id, capture_id)
        photo_path.parent.mkdir(parents=True, exist_ok=True)
        self._validate_jpeg(photo)
        fd, temp_name = tempfile.mkstemp(prefix=f".{capture_id}.", suffix=".tmp", dir=photo_path.parent)
        temp_path = Path(temp_name)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(photo)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_path, photo_path)
            with self.db.connect() as conn:
                conn.execute("BEGIN IMMEDIATE")
                batch = conn.execute(
                    "SELECT expected_count,state,cataloged_at FROM mobile_incoming_batches WHERE batch_uuid=?",
                    (batch_id,),
                ).fetchone()
                if not batch:
                    raise IncomingCaptureError("batch_not_found", 404)
                existing = conn.execute(
                    "SELECT batch_uuid,sequence,isbn,captured_at FROM mobile_incoming_captures WHERE capture_uuid=?",
                    (capture_id,),
                ).fetchone()
                if existing:
                    if (existing["batch_uuid"], existing["sequence"], existing["isbn"], existing["captured_at"]) != (
                        batch_id, sequence, isbn, captured_at
                    ):
                        raise IncomingCaptureError("capture_conflict", 409)
                else:
                    if batch["state"] != "receiving":
                        raise IncomingCaptureError("batch_not_receiving", 409)
                    conn.execute(
                        """INSERT INTO mobile_incoming_captures
                           (capture_uuid,batch_uuid,sequence,isbn,captured_at,photo_name)
                           VALUES(?,?,?,?,?,?)""",
                        (capture_id, batch_id, sequence, isbn, captured_at, f"{capture_id}.jpg"),
                    )
                count = conn.execute(
                    "SELECT COUNT(*) FROM mobile_incoming_captures WHERE batch_uuid=?", (batch_id,)
                ).fetchone()[0]
                if count == batch["expected_count"]:
                    conn.execute(
                        "UPDATE mobile_incoming_batches SET state='ready',updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE batch_uuid=?",
                        (batch_id,),
                    )
        except sqlite3.IntegrityError as exc:
            raise IncomingCaptureError("capture_conflict", 409) from exc
        finally:
            temp_path.unlink(missing_ok=True)
        with self.db.connect() as conn:
            batch = conn.execute(
                "SELECT state,cataloged_at FROM mobile_incoming_batches WHERE batch_uuid=?", (batch_id,)
            ).fetchone()
        return {
            "ok": True,
            "capture_id": capture_id,
            "received": True,
            "duplicate": False,
            "ready": batch["state"] == "ready" and batch["cataloged_at"] is None,
        }

    @staticmethod
    def _validate_jpeg(data: bytes) -> None:
        try:
            import io
            with Image.open(io.BytesIO(data)) as image:
                if image.format != "JPEG":
                    raise IncomingCaptureError("jpeg_required", 415)
                if image.width * image.height > 50_000_000:
                    raise IncomingCaptureError("invalid_photo_dimensions", 413)
                image.verify()
        except IncomingCaptureError:
            raise
        except Exception as exc:
            raise IncomingCaptureError("invalid_photo") from exc

    def _photo_path(self, batch_id: str, capture_id: str) -> Path:
        path = self.root / f"batch-{batch_id}" / f"{capture_id}.jpg"
        path.resolve().relative_to(self.root.resolve())
        return path

    def complete_batch(self, batch_id: Any) -> dict:
        batch_id = self._uuid(batch_id, "batch_id")
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            batch = conn.execute(
                "SELECT expected_count,state,cataloged_at FROM mobile_incoming_batches WHERE batch_uuid=?",
                (batch_id,),
            ).fetchone()
            if not batch:
                raise IncomingCaptureError("batch_not_found", 404)
            count = conn.execute(
                "SELECT COUNT(*) FROM mobile_incoming_captures WHERE batch_uuid=?",
                (batch_id,),
            ).fetchone()[0]
            sequences = [
                row[0]
                for row in conn.execute(
                    "SELECT sequence FROM mobile_incoming_captures WHERE batch_uuid=? ORDER BY sequence",
                    (batch_id,),
                )
            ]
            if batch["state"] == "receiving":
                if count != batch["expected_count"] or sequences != list(range(1, batch["expected_count"] + 1)):
                    raise IncomingCaptureError("batch_incomplete", 409)
                conn.execute(
                    "UPDATE mobile_incoming_batches SET state='ready',updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE batch_uuid=?",
                    (batch_id,),
                )
            elif batch["state"] != "ready":
                raise IncomingCaptureError("batch_not_ready", 409)
        return {
            "ok": True,
            "batch_id": batch_id,
            "received_count": count,
            "ready": True,
            "cataloged": batch["cataloged_at"] is not None,
        }

    def ready_batches(self) -> list[str]:
        with self.db.connect() as conn:
            return [
                row[0]
                for row in conn.execute(
                    "SELECT batch_uuid FROM mobile_incoming_batches WHERE state='ready' AND cataloged_at IS NULL ORDER BY created_at,batch_uuid"
                )
            ]

    def pending_captures(self, batch_id: str) -> list[dict]:
        batch_id = self._uuid(batch_id, "batch_id")
        with self.db.connect() as conn:
            rows = conn.execute(
                """SELECT i.capture_uuid,i.sequence,i.isbn,i.captured_at,i.photo_name
                   FROM mobile_incoming_captures i
                   LEFT JOIN copies c ON c.copy_uuid=i.capture_uuid
                   WHERE i.batch_uuid=? AND c.copy_uuid IS NULL
                   ORDER BY i.sequence""",
                (batch_id,),
            ).fetchall()
        return [
            {**dict(row), "photo_path": self._photo_path(batch_id, row["capture_uuid"])}
            for row in rows
        ]

    def finish_cataloged_capture(self, capture_id: str) -> bool:
        capture_id = self._uuid(capture_id, "capture_id")
        with self.db.connect() as conn:
            row = conn.execute(
                """SELECT i.batch_uuid,c.copy_uuid,c.id AS copy_id,c.photo_path
                   FROM mobile_incoming_captures i
                   LEFT JOIN copies c ON c.copy_uuid=i.capture_uuid
                   WHERE i.capture_uuid=?""",
                (capture_id,),
            ).fetchone()
            if not row or row["copy_uuid"] is None:
                return False
            if conn.execute(
                "SELECT 1 FROM storage_operations WHERE copy_id=? LIMIT 1", (row["copy_id"],)
            ).fetchone():
                return False
        canonical = self.data_dir / row["photo_path"]
        if not canonical.is_file():
            return False
        self._photo_path(row["batch_uuid"], capture_id).unlink(missing_ok=True)
        return True

    def has_unresolved_catalog_save(self, batch_id: str) -> bool:
        batch_id = self._uuid(batch_id, "batch_id")
        with self.db.connect() as conn:
            rows = conn.execute(
                """SELECT i.capture_uuid,c.id AS copy_id,c.photo_path
                   FROM mobile_incoming_captures i JOIN copies c ON c.copy_uuid=i.capture_uuid
                   WHERE i.batch_uuid=?""",
                (batch_id,),
            ).fetchall()
            for row in rows:
                if conn.execute(
                    "SELECT 1 FROM storage_operations WHERE copy_id=? LIMIT 1", (row["copy_id"],)
                ).fetchone():
                    return True
                if not (self.data_dir / row["photo_path"]).is_file():
                    return True
        return False

    def finish_batch_if_empty(self, batch_id: str) -> bool:
        batch_id = self._uuid(batch_id, "batch_id")
        with self.db.connect() as conn:
            if conn.execute(
                """SELECT 1 FROM mobile_incoming_captures i
                   LEFT JOIN copies c ON c.copy_uuid=i.capture_uuid
                   WHERE i.batch_uuid=? AND c.copy_uuid IS NULL LIMIT 1""",
                (batch_id,),
            ).fetchone():
                return False
            conn.execute(
                "UPDATE mobile_incoming_batches SET cataloged_at=COALESCE(cataloged_at,strftime('%Y-%m-%dT%H:%M:%fZ','now')) WHERE batch_uuid=? AND state='ready'",
                (batch_id,),
            )
        return True

    def discard_capture(self, capture_id: str) -> bool:
        capture_id = self._uuid(capture_id, "capture_id")
        with self.db.connect() as conn:
            row = conn.execute(
                """SELECT i.batch_uuid,c.copy_uuid FROM mobile_incoming_captures i
                   LEFT JOIN copies c ON c.copy_uuid=i.capture_uuid WHERE i.capture_uuid=?""",
                (capture_id,),
            ).fetchone()
            if not row or row["copy_uuid"] is not None:
                return False
            batch_id = row["batch_uuid"]
            conn.execute("DELETE FROM mobile_incoming_captures WHERE capture_uuid=?", (capture_id,))
            remaining = conn.execute(
                "SELECT 1 FROM mobile_incoming_captures WHERE batch_uuid=? LIMIT 1", (batch_id,)
            ).fetchone()
            if not remaining:
                conn.execute(
                    "UPDATE mobile_incoming_batches SET cataloged_at=COALESCE(cataloged_at,strftime('%Y-%m-%dT%H:%M:%fZ','now')) WHERE batch_uuid=? AND state='ready'",
                    (batch_id,),
                )
        self._photo_path(batch_id, capture_id).unlink(missing_ok=True)
        return True

    def recover(self) -> None:
        """Remove abandoned upload temp files and finish cleanup after catalog saves."""
        referenced = set()
        with self.db.connect() as conn:
            referenced = {
                (self.root / f"batch-{row['batch_uuid']}" / row['photo_name']).resolve()
                for row in conn.execute("SELECT batch_uuid,photo_name FROM mobile_incoming_captures")
            }
            completed = [
                row[0]
                for row in conn.execute(
                    """SELECT i.capture_uuid FROM mobile_incoming_captures i
                       JOIN copies c ON c.copy_uuid=i.capture_uuid"""
                )
            ]
        for path in self.root.glob("batch-*/*"):
            if path.suffix == ".tmp" or (path.suffix.lower() == ".jpg" and path.resolve() not in referenced):
                path.unlink(missing_ok=True)
        for capture_id in completed:
            self.finish_cataloged_capture(capture_id)

