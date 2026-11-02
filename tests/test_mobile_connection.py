from __future__ import annotations

import http.client
import json
import threading
import time

import pytest

from bookledger.services.mobile_connection import (
    API_PREFIX,
    MobileConnectionService,
    encode_pairing_qr,
)
from bookledger.services.mobile_network import IPv4Candidate


class RecordingAdvertiser:
    def __init__(self):
        self.updates = []
        self.stops = 0

    def update(self, port, addresses):
        self.updates.append((port, tuple(addresses)))

    def stop(self):
        self.stops += 1


class MemoryConfig:
    def __init__(self):
        self.values = {}

    def get(self, path, default=None):
        return self.values.get(tuple(path), default)

    def set(self, path, value):
        self.values[tuple(path)] = value

    def remove(self, path):
        self.values.pop(tuple(path), None)


@pytest.fixture
def service():
    config = MemoryConfig()
    instance = MobileConnectionService(
        config,
        port=0,
        candidate_provider=lambda: [],
        token_protector=lambda value: "protected:" + value,
        token_unprotector=lambda value: value.removeprefix("protected:"),
    )
    instance.start()
    deadline = time.monotonic() + 3
    while instance.status == "starting" and time.monotonic() < deadline:
        time.sleep(0.01)
    assert instance.status == "ready"
    yield instance, config
    instance.stop()


def request(instance, method, path, payload=None, token=None):
    connection = http.client.HTTPConnection(
        "127.0.0.1", instance.active_port, timeout=2
    )
    headers = {}
    body = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload)
    if token is not None:
        headers["Authorization"] = "Bearer " + token
    connection.request(method, path, body=body, headers=headers)
    response = connection.getresponse()
    body = response.read()
    status = response.status
    connection.close()
    return status, json.loads(body) if body else None


def test_dns_sd_advertisement_uses_service_port_and_stops_with_server():
    candidate = IPv4Candidate("192.168.137.1", "Mobile hotspot", "255.255.255.0")
    advertiser = RecordingAdvertiser()
    instance = MobileConnectionService(
        MemoryConfig(),
        port=0,
        candidate_provider=lambda: [candidate],
        token_protector=lambda value: value,
        token_unprotector=lambda value: value,
        discovery_advertiser=advertiser,
    )
    instance.start()
    try:
        deadline = time.monotonic() + 3
        while not advertiser.updates and time.monotonic() < deadline:
            time.sleep(0.01)
        assert advertiser.updates
        assert advertiser.updates[-1] == (
            instance.active_port,
            ("192.168.137.1",),
        )
        assert instance.discovery_status == "advertising"
    finally:
        instance.stop()
    assert advertiser.stops >= 1
    assert instance.discovery_status == "inactive"


def test_pairing_qr_contains_every_candidate_and_only_temporary_credential():
    candidates = [
        IPv4Candidate("192.168.1.20", "Wi-Fi", "255.255.255.0"),
        IPv4Candidate("192.168.137.1", "Mobile hotspot", "255.255.255.0"),
    ]

    payload = json.loads(encode_pairing_qr(candidates, 43821, "temporary-code"))

    assert payload == {
        "protocol": "bookledger-mobile",
        "version": 1,
        "port": 43821,
        "addresses": ["192.168.1.20", "192.168.137.1"],
        "pairing_credential": "temporary-code",
    }
    assert "device_token" not in payload


def test_service_start_is_idempotent_and_health_endpoint_is_available(service):
    instance, _config = service
    thread = instance._thread
    port = instance.active_port

    instance.start()

    assert instance.status == "ready"
    assert instance._thread is thread
    assert instance.active_port == port
    assert request(instance, "GET", f"{API_PREFIX}/health") == (
        200,
        {"ok": True, "protocol": "bookledger-mobile", "version": 1},
    )


def test_pairing_consumes_expiring_credential_and_authenticates_device(service):
    instance, config = service
    credential = instance.pairing_credential

    status, paired = request(
        instance,
        "POST",
        f"{API_PREFIX}/pair",
        {"pairing_credential": credential, "device_name": "Poco X6"},
    )

    assert status == 201
    assert paired["paired"] is True
    token = paired["device_token"]
    assert instance.paired
    assert instance.paired_device_name == "Poco X6"
    assert config.values[("mobile_pairing",)]["token"] == "protected:" + token
    assert request(
        instance, "GET", f"{API_PREFIX}/connection", token=token
    )[0] == 200
    assert request(
        instance, "GET", f"{API_PREFIX}/connection", token="invalid"
    ) == (401, {"error": "unauthorized"})


def test_second_device_is_rejected_until_explicit_unpair(service):
    instance, _config = service
    first = instance.pairing_credential
    assert request(
        instance,
        "POST",
        f"{API_PREFIX}/pair",
        {"pairing_credential": first, "device_name": "First"},
    )[0] == 201

    assert request(
        instance,
        "POST",
        f"{API_PREFIX}/pair",
        {"pairing_credential": first, "device_name": "Second"},
    ) == (409, {"error": "device_already_paired"})


def test_expired_pairing_credential_is_rejected():
    now = [100.0]
    instance = MobileConnectionService(
        MemoryConfig(),
        port=0,
        candidate_provider=lambda: [],
        pairing_lifetime_seconds=1,
        clock=lambda: now[0],
        token_protector=lambda value: value,
        token_unprotector=lambda value: value,
    )
    instance.start()
    try:
        deadline = time.monotonic() + 3
        while instance.status == "starting" and time.monotonic() < deadline:
            time.sleep(0.01)
        credential = instance.pairing_credential
        now[0] = 102.0
        assert credential
        assert instance.pairing_credential == ""
        assert request(
            instance,
            "POST",
            f"{API_PREFIX}/pair",
            {"pairing_credential": credential, "device_name": "Device"},
        ) == (401, {"error": "pairing_rejected"})
    finally:
        instance.stop()


def test_unpair_revokes_token_and_issues_fresh_temporary_credential(service):
    instance, config = service
    credential = instance.pairing_credential
    _status, result = request(
        instance,
        "POST",
        f"{API_PREFIX}/pair",
        {"pairing_credential": credential, "device_name": "Phone"},
    )
    token = result["device_token"]

    assert request(
        instance, "DELETE", f"{API_PREFIX}/pair", token=token
    ) == (200, {"ok": True, "paired": False})
    assert not instance.paired
    assert ("mobile_pairing",) not in config.values
    assert instance.pairing_credential
    assert request(
        instance, "GET", f"{API_PREFIX}/connection", token=token
    ) == (401, {"error": "unauthorized"})


@pytest.mark.parametrize(
    ("payload", "expected_status"),
    [
        (None, 415),
        ([], 400),
        ({"pairing_credential": 2, "device_name": "Phone"}, 400),
        ({"pairing_credential": "a", "device_name": " "}, 400),
        ({"pairing_credential": "a", "device_name": "x" * 81}, 400),
    ],
)
def test_pairing_validates_content_and_payload(service, payload, expected_status):
    instance, _config = service

    status, _body = request(
        instance, "POST", f"{API_PREFIX}/pair", payload=payload
    )

    assert status == expected_status


def test_unreadable_saved_pairing_requires_explicit_desktop_reset():
    config = MemoryConfig()
    config.values[("mobile_pairing",)] = {
        "name": "Old phone",
        "token": "dpapi:v1:invalid",
    }

    def reject_token(_value):
        raise ValueError("cannot decrypt")

    instance = MobileConnectionService(
        config,
        port=0,
        candidate_provider=lambda: [],
        token_protector=lambda value: value,
        token_unprotector=reject_token,
    )
    assert instance.needs_pairing_reset
    instance.start()
    deadline = time.monotonic() + 3
    while instance.status == "starting" and time.monotonic() < deadline:
        time.sleep(0.01)
    original_thread = instance._thread
    instance.start()
    assert instance._thread is original_thread
    assert instance.status == "error"

    instance.unpair()

    assert not instance.needs_pairing_reset
    assert ("mobile_pairing",) not in config.values
    assert instance.status == "ready"
    assert instance.pairing_credential
    instance.stop()


def test_unknown_endpoints_do_not_expose_transfer(service):
    instance, _config = service

    assert request(instance, "POST", f"{API_PREFIX}/transfer", {}) == (
        404,
        {"error": "not_found"},
    )
    assert request(instance, "GET", f"{API_PREFIX}/books")[0] == 404


def test_stop_releases_listener_and_invalidates_temporary_credential():
    config = MemoryConfig()
    instance = MobileConnectionService(
        config,
        port=0,
        candidate_provider=lambda: [],
        token_protector=lambda value: value,
        token_unprotector=lambda value: value,
    )
    instance.start()
    deadline = time.monotonic() + 3
    while instance.status == "starting" and time.monotonic() < deadline:
        time.sleep(0.01)
    port = instance.active_port
    assert instance.pairing_credential

    instance.stop()

    assert instance.status == "inactive"
    assert instance.pairing_credential == ""
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=1)
    with pytest.raises(OSError):
        connection.request("GET", f"{API_PREFIX}/health")
    connection.close()
