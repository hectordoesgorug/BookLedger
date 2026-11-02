from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import ipaddress
import os


_AF_INET = 2
_ERROR_BUFFER_OVERFLOW = 111
_GAA_FLAGS = 0x2 | 0x4 | 0x8 | 0x10
_IF_OPER_STATUS_UP = 1


class _SocketAddress(ctypes.Structure):
    _fields_ = [("sockaddr", ctypes.c_void_p), ("length", ctypes.c_int)]


class _AdapterUnicast(ctypes.Structure):
    _fields_ = [
        ("length", wintypes.ULONG),
        ("flags", wintypes.DWORD),
        ("next", ctypes.c_void_p),
        ("address", _SocketAddress),
        ("prefix_origin", ctypes.c_int),
        ("suffix_origin", ctypes.c_int),
        ("dad_state", ctypes.c_int),
        ("valid_lifetime", wintypes.ULONG),
        ("preferred_lifetime", wintypes.ULONG),
        ("lease_lifetime", wintypes.ULONG),
        ("on_link_prefix_length", ctypes.c_ubyte),
    ]


class _AdapterAddresses(ctypes.Structure):
    _fields_ = [
        ("length", wintypes.ULONG),
        ("if_index", wintypes.DWORD),
        ("next", ctypes.c_void_p),
        ("adapter_name", ctypes.c_char_p),
        ("first_unicast_address", ctypes.c_void_p),
        ("first_anycast_address", ctypes.c_void_p),
        ("first_multicast_address", ctypes.c_void_p),
        ("first_dns_server_address", ctypes.c_void_p),
        ("dns_suffix", wintypes.LPWSTR),
        ("description", wintypes.LPWSTR),
        ("friendly_name", wintypes.LPWSTR),
        ("physical_address", ctypes.c_ubyte * 8),
        ("physical_address_length", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("mtu", wintypes.DWORD),
        ("if_type", wintypes.DWORD),
        ("oper_status", wintypes.DWORD),
        ("ipv6_if_index", wintypes.DWORD),
        ("zone_indices", wintypes.DWORD * 16),
        ("first_prefix", ctypes.c_void_p),
    ]


class _SockaddrIn(ctypes.Structure):
    _fields_ = [
        ("family", ctypes.c_ushort),
        ("port", ctypes.c_ushort),
        ("address", ctypes.c_ubyte * 4),
        ("zero", ctypes.c_ubyte * 8),
    ]


@dataclass(frozen=True)
class IPv4Candidate:
    """A usable local IPv4 address and the subnet on which it can be reached."""

    address: str
    interface: str
    netmask: str

    @property
    def network(self) -> ipaddress.IPv4Network | None:
        try:
            return ipaddress.IPv4Network(f"{self.address}/{self.netmask}", strict=False)
        except (ipaddress.AddressValueError, ipaddress.NetmaskValueError):
            return None


def candidate_for_address(
    address: str, prefix_length: int, interface: str
) -> IPv4Candidate | None:
    """Filter an adapter address and derive its subnet mask."""
    try:
        ip = ipaddress.IPv4Address(address)
        if not 1 <= prefix_length <= 32:
            return None
        network = ipaddress.IPv4Network(f"{ip}/{prefix_length}", strict=False)
    except (ipaddress.AddressValueError, ipaddress.NetmaskValueError):
        return None
    if (
        ip.is_loopback
        or ip.is_unspecified
        or ip.is_multicast
        or ip.is_link_local
        or ip.is_reserved
        or not ip.is_private
        or ip == network.network_address
        or ip == network.broadcast_address
    ):
        return None
    return IPv4Candidate(str(ip), interface, str(network.netmask))


def _iter_windows_ipv4_addresses():
    if os.name != "nt":
        return
    iphlpapi = ctypes.WinDLL("iphlpapi", use_last_error=True)
    get_adapters = iphlpapi.GetAdaptersAddresses
    get_adapters.argtypes = [
        wintypes.ULONG,
        wintypes.ULONG,
        ctypes.c_void_p,
        ctypes.POINTER(_AdapterAddresses),
        ctypes.POINTER(wintypes.ULONG),
    ]
    get_adapters.restype = wintypes.ULONG
    buffer_size = wintypes.ULONG(15_000)
    result = get_adapters(
        _AF_INET, _GAA_FLAGS, None, None, ctypes.byref(buffer_size)
    )
    if result != _ERROR_BUFFER_OVERFLOW:
        if result == 0:
            return
        raise OSError(result, "Windows could not enumerate IPv4 adapters.")
    buffer = ctypes.create_string_buffer(buffer_size.value)
    first = ctypes.cast(buffer, ctypes.POINTER(_AdapterAddresses))
    result = get_adapters(
        _AF_INET, _GAA_FLAGS, None, first, ctypes.byref(buffer_size)
    )
    if result != 0:
        raise OSError(result, "Windows could not enumerate IPv4 adapters.")

    adapter_pointer = ctypes.cast(first, ctypes.c_void_p)
    while adapter_pointer:
        adapter = ctypes.cast(
            adapter_pointer, ctypes.POINTER(_AdapterAddresses)
        ).contents
        if adapter.oper_status == _IF_OPER_STATUS_UP:
            interface = adapter.friendly_name or adapter.adapter_name or "Network"
            unicast_pointer = adapter.first_unicast_address
            while unicast_pointer:
                unicast = ctypes.cast(
                    unicast_pointer, ctypes.POINTER(_AdapterUnicast)
                ).contents
                if unicast.address.sockaddr and unicast.address.length >= 16:
                    sockaddr = ctypes.cast(
                        unicast.address.sockaddr, ctypes.POINTER(_SockaddrIn)
                    ).contents
                    if sockaddr.family == _AF_INET:
                        address = str(ipaddress.IPv4Address(bytes(sockaddr.address)))
                        yield address, int(unicast.on_link_prefix_length), interface
                unicast_pointer = unicast.next
        adapter_pointer = adapter.next


def discover_ipv4_candidates() -> list[IPv4Candidate]:
    """Enumerate active private IPv4 addresses on Windows in adapter order."""
    candidates: list[IPv4Candidate] = []
    seen: set[tuple[str, str]] = set()
    try:
        addresses = _iter_windows_ipv4_addresses()
        for address, prefix_length, interface in addresses:
            candidate = candidate_for_address(address, prefix_length, interface)
            if candidate is None:
                continue
            key = (candidate.address, candidate.netmask)
            if key in seen:
                continue
            seen.add(key)
            candidates.append(candidate)
    except OSError:
        return []
    return candidates


def is_local_peer(peer: str, candidates: list[IPv4Candidate]) -> bool:
    """Check that an IPv4 peer belongs to one of the machine's local subnets."""
    try:
        address = ipaddress.IPv4Address(peer)
    except ipaddress.AddressValueError:
        return False
    if address.is_loopback:
        return True
    return any(
        (network := candidate.network) is not None and address in network
        for candidate in candidates
    )
