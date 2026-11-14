from __future__ import annotations

from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import json
import re
import secrets
import threading
import time
from typing import Callable

from bookledger.services.credential_protection import protect_secret, unprotect_secret
from bookledger.services.mobile_discovery import MdnsServiceAdvertiser
from bookledger.services.mobile_network import IPv4Candidate, discover_ipv4_candidates, is_local_peer


API_PREFIX = "/api/v1"
PROTOCOL_ID = "bookledger-mobile"
DEFAULT_PORT = 43821
MAX_REQUEST_BYTES = 8 * 1024
MAX_UPLOAD_BYTES = 25 * 1024 * 1024 + 64 * 1024


def encode_pairing_qr(
    candidates: list[IPv4Candidate], port: int, pairing_credential: str
) -> str:
    if not candidates or not 1 <= port <= 65535 or not pairing_credential:
        raise ValueError("Usable addresses, port, and pairing credential are required.")
    return json.dumps(
        {
            "protocol": PROTOCOL_ID,
            "version": 1,
            "port": port,
            "addresses": [candidate.address for candidate in candidates],
            "pairing_credential": pairing_credential,
        },
        separators=(",", ":"),
    )


def _constant_time_equal(supplied: str, expected: str) -> bool:
    try:
        return hmac.compare_digest(
            supplied.encode("utf-8", errors="strict"),
            expected.encode("utf-8", errors="strict"),
        )
    except UnicodeError:
        return False


class _ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True
    block_on_close = False


class MobileConnectionService:
    """Local-only pairing and connection API for the Android companion."""

    def __init__(
        self,
        config_store,
        *,
        port: int = DEFAULT_PORT,
        candidate_provider: Callable[[], list[IPv4Candidate]] = discover_ipv4_candidates,
        pairing_lifetime_seconds: int = 300,
        clock: Callable[[], float] = time.monotonic,
        token_protector: Callable[[str], str] = protect_secret,
        token_unprotector: Callable[[str], str] = unprotect_secret,
        discovery_advertiser=None,
        incoming_store=None,
        on_reception_change: Callable[[bool], None] | None = None,
        on_batch_ready: Callable[[str], None] | None = None,
        on_activity: Callable[[str], None] | None = None,
        on_state_change: Callable[[], None] | None = None,
    ):
        if not 0 <= port <= 65535:
            raise ValueError("The mobile service port is invalid.")
        if pairing_lifetime_seconds <= 0:
            raise ValueError("The pairing credential lifetime must be positive.")
        self.config_store = config_store
        self.port = port
        self.candidate_provider = candidate_provider
        self.pairing_lifetime_seconds = pairing_lifetime_seconds
        self._clock = clock
        self._token_protector = token_protector
        self._token_unprotector = token_unprotector
        self._discovery_advertiser = discovery_advertiser or MdnsServiceAdvertiser()
        self.incoming_store = incoming_store
        self.on_reception_change = on_reception_change
        self.on_batch_ready = on_batch_ready
        self.on_activity = on_activity
        self.on_state_change = on_state_change
        self._active_receivers = 0
        self._discovery_status = "inactive"
        self._lock = threading.RLock()
        self._server: _ReusableThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._network_refresh_stop = threading.Event()
        self._network_refresh_thread: threading.Thread | None = None
        self._status = "inactive"
        self._error = ""
        self._pairing_credential = ""
        self._pairing_expires_at = 0.0
        self._paired_device: dict | None = None
        self._token = ""
        self._saved_pairing_invalid = False
        self._candidates: list[IPv4Candidate] = []
        self._load_existing_pairing()

    @property
    def status(self) -> str:
        with self._lock:
            return self._status

    @property
    def error(self) -> str:
        with self._lock:
            return self._error

    @property
    def discovery_status(self) -> str:
        with self._lock:
            return self._discovery_status

    @property
    def pairing_credential(self) -> str:
        with self._lock:
            if not self._pairing_is_valid_locked():
                return ""
            return self._pairing_credential

    @property
    def pairing_expires_at(self) -> float:
        with self._lock:
            return self._pairing_expires_at

    @property
    def paired_device_name(self) -> str:
        with self._lock:
            return str((self._paired_device or {}).get("name", ""))

    @property
    def paired(self) -> bool:
        with self._lock:
            return self._paired_device is not None

    @property
    def needs_pairing_reset(self) -> bool:
        with self._lock:
            return self._saved_pairing_invalid

    @property
    def candidates(self) -> list[IPv4Candidate]:
        with self._lock:
            return list(self._candidates)

    def refresh_candidates(self) -> list[IPv4Candidate]:
        try:
            candidates = self.candidate_provider()
        except Exception:
            candidates = []
        with self._lock:
            self._candidates = list(candidates)
            return list(self._candidates)

    @property
    def active_port(self) -> int:
        with self._lock:
            return self._server.server_address[1] if self._server else self.port

    def _load_existing_pairing(self) -> None:
        try:
            record = self.config_store.get(("mobile_pairing",), None)
            if record is None:
                return
            if not isinstance(record, dict):
                raise ValueError("Stored desktop pairing data is invalid.")
            protected = record.get("token")
            name = record.get("name")
            if not isinstance(protected, str) or not isinstance(name, str) or not name:
                raise ValueError("Stored desktop pairing data is invalid.")
            token = self._token_unprotector(protected)
            if len(token) < 40:
                raise ValueError("Stored desktop pairing token is invalid.")
        except Exception as exc:
            self._saved_pairing_invalid = True
            self._status = "error"
            self._error = f"Saved pairing data could not be read ({type(exc).__name__})."
            return
        self._token = token
        self._paired_device = {"name": name}

    def _pairing_is_valid_locked(self) -> bool:
        if self._pairing_credential and self._clock() >= self._pairing_expires_at:
            self._pairing_credential = ""
            self._pairing_expires_at = 0.0
        return bool(
            self._pairing_credential
            and self._paired_device is None
            and not self._saved_pairing_invalid
        )

    def _notify_state_change(self) -> None:
        if self.on_state_change is not None:
            try:
                self.on_state_change()
            except Exception:
                pass

    def _record_activity(self, event: str) -> None:
        if self.on_activity is not None:
            try:
                self.on_activity(event)
            except Exception:
                pass

    def _new_pairing_credential_locked(self) -> None:
        self._pairing_credential = secrets.token_urlsafe(32)
        self._pairing_expires_at = self._clock() + self.pairing_lifetime_seconds

    def start(self) -> None:
        with self._lock:
            if self._server is not None or self._status in (
                "starting",
                "ready",
                "paired",
            ):
                return
            self._status = "starting"
            if not self._saved_pairing_invalid:
                self._error = ""
                if self._paired_device is None:
                    self._new_pairing_credential_locked()
            self._network_refresh_stop.clear()
            self._network_refresh_thread = threading.Thread(
                target=self._refresh_network_loop,
                name="BookLedgerMobileInterfaces",
                daemon=True,
            )
            self._network_refresh_thread.start()
            self._thread = threading.Thread(
                target=self._serve,
                name="BookLedgerMobileHttp",
                daemon=True,
            )
            self._thread.start()
        self._notify_state_change()

    def _refresh_network_loop(self) -> None:
        while not self._network_refresh_stop.is_set():
            self.refresh_candidates()
            self._sync_discovery()
            if self._network_refresh_stop.wait(5.0):
                return

    def _sync_discovery(self) -> None:
        with self._lock:
            active = self._server is not None and self._status in ("ready", "paired")
            candidates = list(self._candidates)
            port = self._server.server_address[1] if self._server else 0
        if not active or not candidates:
            try:
                self._discovery_advertiser.stop()
                state = "unavailable" if active else "inactive"
            except Exception as exc:
                state = f"error ({type(exc).__name__})"
        else:
            try:
                self._discovery_advertiser.update(
                    port, [candidate.address for candidate in candidates]
                )
                state = "advertising"
            except Exception as exc:
                state = f"error ({type(exc).__name__})"
        with self._lock:
            self._discovery_status = state

    def _serve(self) -> None:
        service = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "BookLedgerMobile/1"
            sys_version = ""

            def setup(self):
                super().setup()
                self.connection.settimeout(3.0)

            def log_message(self, _format, *_args):
                return

            def _write_json(self, status: int, payload: dict) -> None:
                body = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(body)
                self.close_connection = True

            def _peer_is_local(self) -> bool:
                peer = self.client_address[0]
                return is_local_peer(peer, service.candidates)

            def _authorized(self) -> bool:
                header = self.headers.get("Authorization", "")
                scheme, separator, supplied = header.partition(" ")
                if not separator or scheme.casefold() != "bearer" or not supplied:
                    return False
                with service._lock:
                    current = service._token
                    return bool(current) and _constant_time_equal(supplied, current)

            def _body_bytes(self, limit: int) -> bytes | None:
                try:
                    length = int(self.headers.get("Content-Length", ""))
                except ValueError:
                    self._write_json(400, {"error": "invalid_content_length"})
                    return None
                if length < 0 or length > limit:
                    self._write_json(413, {"error": "request_too_large"})
                    return None
                body = self.rfile.read(length)
                if len(body) != length:
                    self._write_json(400, {"error": "incomplete_request"})
                    return None
                return body

            def _json_body(self) -> dict | None:
                content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
                if content_type != "application/json":
                    self._write_json(415, {"error": "content_type_required"})
                    return None
                raw = self._body_bytes(MAX_REQUEST_BYTES)
                if raw is None:
                    return None
                try:
                    value = json.loads(raw)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    self._write_json(400, {"error": "invalid_json"})
                    return None
                if not isinstance(value, dict):
                    self._write_json(400, {"error": "object_required"})
                    return None
                return value

            def _incoming_error(self, error):
                self._write_json(error.status, {"error": error.code})

            def _set_receiving(self, active: bool):
                with service._lock:
                    service._active_receivers += 1 if active else -1
                    changed = service._active_receivers == 1 if active else service._active_receivers == 0
                if changed and service.on_reception_change is not None:
                    service.on_reception_change(active)
                if changed and active:
                    service._record_activity("reception_started")

            def do_GET(self):
                if not self._peer_is_local():
                    self._write_json(403, {"error": "local_network_only"})
                    return
                if self.path == f"{API_PREFIX}/health":
                    self._write_json(
                        200,
                        {"ok": True, "protocol": PROTOCOL_ID, "version": 1},
                    )
                    return
                if self.path != f"{API_PREFIX}/connection":
                    self._write_json(404, {"error": "not_found"})
                    return
                if not self._authorized():
                    self._write_json(401, {"error": "unauthorized"})
                    return
                self._write_json(
                    200,
                    {
                        "ok": True,
                        "paired_device": service.paired_device_name,
                        "server_time": datetime.now(timezone.utc).isoformat(),
                    },
                )

            def do_POST(self):
                if not self._peer_is_local():
                    self._write_json(403, {"error": "local_network_only"})
                    return
                if not self._authorized() and self.path.startswith(f"{API_PREFIX}/batches"):
                    self._write_json(401, {"error": "unauthorized"})
                    return
                if self.path == f"{API_PREFIX}/pair":
                    payload = self._json_body()
                    if payload is None:
                        return
                    supplied = payload.get("pairing_credential")
                    name = payload.get("device_name")
                    if (
                        not isinstance(supplied, str)
                        or not isinstance(name, str)
                        or not name.strip()
                        or len(name.strip()) > 80
                    ):
                        self._write_json(400, {"error": "invalid_pairing_request"})
                        return
                    response, status = service._pair(supplied, name.strip())
                    self._write_json(status, response)
                    return
                store = service.incoming_store
                if store is None:
                    self._write_json(404, {"error": "not_found"})
                    return
                try:
                    if self.path == f"{API_PREFIX}/batches":
                        payload = self._json_body()
                        if payload is None:
                            return
                        result = store.begin_batch(payload.get("batch_id"), payload.get("expected_count"))
                        service._record_activity("batch_started")
                        self._write_json(201, result)
                        return
                    match = re.fullmatch(
                        re.escape(f"{API_PREFIX}/batches/") + r"([0-9a-fA-F-]{36})/captures/([0-9a-fA-F-]{36})",
                        self.path,
                    )
                    if match:
                        self.connection.settimeout(30.0)
                        self._set_receiving(True)
                        try:
                            content_type = self.headers.get("Content-Type", "")
                            raw = self._body_bytes(MAX_UPLOAD_BYTES)
                            if raw is None:
                                service._record_activity("reception_failed")
                                return
                            result = store.receive_capture(match.group(1), match.group(2), content_type, raw)
                            service._record_activity("capture_received")
                        finally:
                            self._set_receiving(False)
                        self._write_json(200, result)
                        if result.get("ready") and service.on_batch_ready is not None:
                            service.on_batch_ready(match.group(1))
                        return
                    match = re.fullmatch(
                        re.escape(f"{API_PREFIX}/batches/") + r"([0-9a-fA-F-]{36})/complete",
                        self.path,
                    )
                    if match:
                        payload = self._json_body()
                        if payload is None:
                            return
                        result = store.complete_batch(match.group(1))
                        service._record_activity("transfer_completed")
                        self._write_json(200, result)
                        return
                    self._write_json(404, {"error": "not_found"})
                except Exception as exc:
                    from bookledger.services.mobile_incoming import IncomingCaptureError
                    if isinstance(exc, IncomingCaptureError):
                        service._record_activity("reception_failed")
                        self._incoming_error(exc)
                    else:
                        service._record_activity("reception_failed")
                        self._write_json(500, {"error": "incoming_storage_failed"})

            def do_DELETE(self):
                if not self._peer_is_local():
                    self._write_json(403, {"error": "local_network_only"})
                    return
                if self.path != f"{API_PREFIX}/pair":
                    self._write_json(404, {"error": "not_found"})
                    return
                if not self._authorized():
                    self._write_json(401, {"error": "unauthorized"})
                    return
                service.unpair()
                self._write_json(200, {"ok": True, "paired": False})

        try:
            server = _ReusableThreadingHTTPServer(
                ("0.0.0.0", self.port), Handler
            )
            server.timeout = 0.25
            with self._lock:
                if self._status == "stopping":
                    server.server_close()
                    return
                self._server = server
                self.port = server.server_address[1]
                self._status = (
                    "error"
                    if self._saved_pairing_invalid
                    else "paired"
                    if self._paired_device
                    else "ready"
                )
            self._notify_state_change()
            self.refresh_candidates()
            self._sync_discovery()
            server.serve_forever(poll_interval=0.25)
        except OSError as exc:
            with self._lock:
                if self._status != "stopping":
                    self._status = "error"
                    self._error = f"Could not start the local service ({type(exc).__name__})."
            self._notify_state_change()
        finally:
            self._network_refresh_stop.set()
            try:
                self._discovery_advertiser.stop()
            except Exception:
                pass
            with self._lock:
                self._discovery_status = "inactive"
                server = self._server
                self._server = None
                if self._status == "stopping":
                    self._status = "inactive"
            self._notify_state_change()
            if server is not None:
                server.server_close()

    def _pair(self, supplied: str, device_name: str) -> tuple[dict, int]:
        with self._lock:
            if self._saved_pairing_invalid:
                return {"error": "saved_pairing_unreadable"}, 409
            if self._paired_device is not None:
                return {"error": "device_already_paired"}, 409
            if not self._pairing_is_valid_locked() or not _constant_time_equal(
                supplied, self._pairing_credential
            ):
                return {"error": "pairing_rejected"}, 401
            token = secrets.token_urlsafe(48)
            protected = self._token_protector(token)
            record = {"name": device_name, "token": protected}
            try:
                self.config_store.set(("mobile_pairing",), record)
            except Exception:
                return {"error": "pairing_storage_failed"}, 500
            self._token = token
            self._paired_device = {"name": device_name}
            self._pairing_credential = ""
            self._pairing_expires_at = 0.0
            self._status = "paired"
        self._record_activity("pairing_established")
        self._notify_state_change()
        return {"device_token": token, "paired": True}, 201

    def refresh_pairing_credential(self) -> str:
        with self._lock:
            if self._paired_device is not None or self._server is None:
                return ""
            self._new_pairing_credential_locked()
            return self._pairing_credential

    def unpair(self) -> None:
        with self._lock:
            self.config_store.remove(("mobile_pairing",))
            self._token = ""
            self._paired_device = None
            self._saved_pairing_invalid = False
            self._error = ""
            self._pairing_credential = ""
            self._pairing_expires_at = 0.0
            if self._server is not None:
                self._new_pairing_credential_locked()
                self._status = "ready"
            else:
                self._status = "inactive"
        self._record_activity("device_unpaired")
        self._notify_state_change()

    def stop(self) -> None:
        with self._lock:
            self._status = "stopping"
            self._pairing_credential = ""
            self._pairing_expires_at = 0.0
            server = self._server
            thread = self._thread
            network_thread = self._network_refresh_thread
            self._network_refresh_stop.set()
        if server is not None:
            server.shutdown()
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2.0)
        if (
            network_thread is not None
            and network_thread is not threading.current_thread()
        ):
            network_thread.join(timeout=1.0)
        try:
            self._discovery_advertiser.stop()
        except Exception:
            pass
        with self._lock:
            self._discovery_status = "inactive"
            self._server = None
            self._thread = None
            self._network_refresh_thread = None
            self._status = "inactive"
        self._notify_state_change()
