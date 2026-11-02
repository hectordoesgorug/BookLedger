from __future__ import annotations

import pytest

from bookledger.services import mobile_network


def test_candidate_accepts_wifi_and_windows_hotspot_addresses():
    wifi = mobile_network.candidate_for_address("192.168.1.45", 24, "Wi-Fi")
    hotspot = mobile_network.candidate_for_address(
        "192.168.137.1", 24, "Mobile hotspot"
    )

    assert wifi is not None
    assert wifi.network.with_prefixlen == "192.168.1.0/24"
    assert hotspot is not None
    assert hotspot.network.with_prefixlen == "192.168.137.0/24"


@pytest.mark.parametrize(
    ("address", "prefix_length"),
    [
        ("127.0.0.1", 8),
        ("0.0.0.0", 0),
        ("169.254.2.4", 16),
        ("224.0.0.1", 24),
        ("192.168.1.0", 24),
        ("192.168.1.255", 24),
        ("192.168.1.45", 33),
        ("not-an-ip", 24),
    ],
)
def test_candidate_rejects_unsuitable_addresses(address, prefix_length):
    assert mobile_network.candidate_for_address(address, prefix_length, "Wi-Fi") is None


def test_discovery_preserves_distinct_interfaces_and_deduplicates(monkeypatch):
    monkeypatch.setattr(
        mobile_network,
        "_iter_windows_ipv4_addresses",
        lambda: iter(
            [
                ("192.168.1.45", 24, "Wi-Fi"),
                ("192.168.137.1", 24, "Mobile hotspot"),
                ("192.168.1.45", 24, "Ethernet"),
            ]
        ),
    )

    candidates = mobile_network.discover_ipv4_candidates()

    assert [(item.address, item.interface) for item in candidates] == [
        ("192.168.1.45", "Wi-Fi"),
        ("192.168.137.1", "Mobile hotspot"),
    ]


def test_discovery_returns_empty_candidates_if_windows_enumeration_fails(monkeypatch):
    def fail():
        raise OSError("unavailable")

    monkeypatch.setattr(mobile_network, "_iter_windows_ipv4_addresses", fail)

    assert mobile_network.discover_ipv4_candidates() == []


def test_is_local_peer_matches_discovered_subnets():
    candidates = [
        mobile_network.IPv4Candidate(
            "192.168.137.1", "Mobile hotspot", "255.255.255.0"
        )
    ]

    assert mobile_network.is_local_peer("192.168.137.42", candidates)
    assert not mobile_network.is_local_peer("10.0.0.8", candidates)
    assert not mobile_network.is_local_peer("not-an-ip", candidates)
