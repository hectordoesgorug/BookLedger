from __future__ import annotations

import http.client
import json
import time
import uuid
from datetime import datetime, timezone
from io import BytesIO

import pytest
from PIL import Image

from bookledger.db.database import Database
from bookledger.services.catalog import CatalogService
from bookledger.services.mobile_connection import MobileConnectionService
from bookledger.services.mobile_incoming import IncomingCaptureError, MobileIncomingStore


def _jpeg(color: str = "navy") -> bytes:
    stream = BytesIO()
    Image.new("RGB", (12, 18), color).save(stream, format="JPEG")
    return stream.getvalue()


def _multipart(metadata: dict, photo: bytes) -> tuple[str, bytes]:
    boundary = "BookLedgerTestBoundary"
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="metadata"; filename="metadata.json"\r\n'
        "Content-Type: application/json\r\n\r\n"
    ).encode() + json.dumps(metadata).encode() + (
        f"\r\n--{boundary}\r\n"
        'Content-Disposition: form-data; name="photo"; filename="capture.jpg"\r\n'
        "Content-Type: image/jpeg\r\n\r\n"
    ).encode() + photo + f"\r\n--{boundary}--\r\n".encode()
    return f"multipart/form-data; boundary={boundary}", body


def _metadata(sequence: int, isbn: str | None) -> dict:
    return {
        "sequence": sequence,
        "isbn": isbn,
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }


@pytest.fixture
def incoming(tmp_path):
    data_dir = tmp_path / "data"
    db = Database(data_dir / "bookledger.sqlite3")
    store = MobileIncomingStore(db, data_dir)
    return db, data_dir, store


def test_receive_order_duplicate_isbns_and_isbn_less_capture_are_durable(incoming):
    _db, _data_dir, store = incoming
    batch_id = str(uuid.uuid4())
    first_id, second_id, third_id = (str(uuid.uuid4()) for _ in range(3))
    store.begin_batch(batch_id, 3)

    for sequence, capture_id, isbn, color in (
        (1, first_id, "9780306406157", "red"),
        (2, second_id, "9780306406157", "green"),
        (3, third_id, None, "blue"),
    ):
        content_type, body = _multipart(_metadata(sequence, isbn), _jpeg(color))
        result = store.receive_capture(batch_id, capture_id, content_type, body)
        assert result["received"] is True
        assert result["duplicate"] is False

    assert store.ready_batches() == [batch_id]
    assert store.complete_batch(batch_id)["ready"] is True
    pending = store.pending_captures(batch_id)
    assert [item["capture_uuid"] for item in pending] == [first_id, second_id, third_id]
    assert [item["isbn"] for item in pending] == [
        "9780306406157",
        "9780306406157",
        None,
    ]
    assert all(item["photo_path"].is_file() for item in pending)
    assert store.ready_batches() == [batch_id]


def test_repeated_capture_request_is_idempotently_acknowledged(incoming):
    _db, _data_dir, store = incoming
    batch_id, capture_id = str(uuid.uuid4()), str(uuid.uuid4())
    store.begin_batch(batch_id, 1)
    content_type, body = _multipart(_metadata(1, None), _jpeg())

    first = store.receive_capture(batch_id, capture_id, content_type, body)
    second = store.receive_capture(batch_id, capture_id, content_type, body)

    assert first["duplicate"] is False
    assert second["duplicate"] is True
    assert len(store.pending_captures(batch_id)) == 1
    assert store.complete_batch(batch_id)["received_count"] == 1


def test_incomplete_batch_and_invalid_payloads_are_rejected(incoming):
    _db, _data_dir, store = incoming
    batch_id = str(uuid.uuid4())
    store.begin_batch(batch_id, 1)
    with pytest.raises(IncomingCaptureError, match="batch_incomplete"):
        store.complete_batch(batch_id)

    content_type, body = _multipart(_metadata(1, "9780306406158"), _jpeg())
    with pytest.raises(IncomingCaptureError, match="invalid_isbn"):
        store.receive_capture(batch_id, str(uuid.uuid4()), content_type, body)

    content_type, body = _multipart(_metadata(1, None), b"not a jpeg")
    with pytest.raises(IncomingCaptureError, match="jpeg_required"):
        store.receive_capture(batch_id, str(uuid.uuid4()), content_type, body)

    with pytest.raises(IncomingCaptureError, match="invalid_capture_id"):
        store.receive_capture(batch_id, "../unsafe", content_type, body)


def test_restart_recovery_keeps_received_batch_and_removes_orphan_uploads(incoming):
    db, data_dir, store = incoming
    batch_id, capture_id = str(uuid.uuid4()), str(uuid.uuid4())
    store.begin_batch(batch_id, 1)
    content_type, body = _multipart(_metadata(1, "9780306406157"), _jpeg())
    store.receive_capture(batch_id, capture_id, content_type, body)
    store.complete_batch(batch_id)
    orphan_dir = data_dir / "incoming" / f"batch-{batch_id}"
    orphan = orphan_dir / f"{uuid.uuid4()}.jpg"
    orphan.write_bytes(_jpeg())

    restarted = MobileIncomingStore(db, data_dir)
    restarted.recover()

    assert restarted.ready_batches() == [batch_id]
    assert len(restarted.pending_captures(batch_id)) == 1
    assert not orphan.exists()


def test_catalog_save_is_recognized_after_restart_without_duplicate_copy(incoming):
    db, data_dir, store = incoming
    batch_id, capture_id = str(uuid.uuid4()), str(uuid.uuid4())
    store.begin_batch(batch_id, 1)
    content_type, body = _multipart(_metadata(1, None), _jpeg())
    store.receive_capture(batch_id, capture_id, content_type, body)
    store.complete_batch(batch_id)
    capture = store.pending_captures(batch_id)[0]
    catalog = CatalogService(db, data_dir)

    copy_id = catalog.create_copy(
        {
            "title": "Incoming Book",
            "author": "Test Author",
            "isbn": None,
            "genre": "Science",
            "format": "Paperback",
            "condition": "Good",
            "location": "",
            "price": "5.00",
            "photo_path": str(capture["photo_path"]),
        },
        copy_uuid=capture_id,
    )
    restarted = MobileIncomingStore(db, data_dir)
    restarted.recover()

    assert catalog.get_copy(copy_id)["copy_uuid"] == capture_id
    assert restarted.pending_captures(batch_id) == []
    assert restarted.finish_batch_if_empty(batch_id) is True
    assert restarted.ready_batches() == []
    duplicate = restarted.receive_capture(batch_id, capture_id, content_type, body)
    assert duplicate["duplicate"] is True
    assert duplicate["ready"] is False
    assert not capture["photo_path"].exists()


def test_authenticated_http_transfer_stages_and_completes_batch(incoming):
    _db, _data_dir, store = incoming
    receiver_states = []
    completed_batches = []
    service = MobileConnectionService(
        object(),
        port=0,
        candidate_provider=lambda: [],
        token_protector=lambda value: value,
        token_unprotector=lambda value: value,
        incoming_store=store,
        on_reception_change=receiver_states.append,
        on_batch_ready=completed_batches.append,
    )
    service._token = "t" * 48
    service.start()
    try:
        deadline = time.monotonic() + 3
        while service.status == "starting" and time.monotonic() < deadline:
            time.sleep(0.01)
        batch_id, capture_id = str(uuid.uuid4()), str(uuid.uuid4())
        connection = http.client.HTTPConnection("127.0.0.1", service.active_port, timeout=3)
        headers = {"Authorization": "Bearer " + "t" * 48, "Content-Type": "application/json"}
        connection.request(
            "POST",
            "/api/v1/batches",
            json.dumps({"batch_id": batch_id, "expected_count": 1}),
            headers,
        )
        response = connection.getresponse()
        assert response.status == 201
        assert json.loads(response.read())["ok"] is True

        content_type, body = _multipart(_metadata(1, None), _jpeg())
        connection.request(
            "POST",
            f"/api/v1/batches/{batch_id}/captures/{capture_id}",
            body,
            {"Authorization": "Bearer " + "t" * 48, "Content-Type": content_type},
        )
        response = connection.getresponse()
        assert response.status == 200
        assert json.loads(response.read())["received"] is True
        connection.request(
            "POST",
            f"/api/v1/batches/{batch_id}/complete",
            "{}",
            {"Authorization": "Bearer " + "t" * 48, "Content-Type": "application/json"},
        )
        response = connection.getresponse()
        assert response.status == 200
        assert json.loads(response.read())["ready"] is True
        connection.close()
    finally:
        service.stop()

    assert receiver_states == [True, False]
    assert completed_batches == [batch_id]
    assert len(store.pending_captures(batch_id)) == 1
