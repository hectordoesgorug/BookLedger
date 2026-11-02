from __future__ import annotations

import ipaddress
import socket
import threading

from zeroconf import InterfaceChoice, ServiceInfo, Zeroconf


SERVICE_TYPE = "_bookledger._tcp.local."
SERVICE_NAME = "BookLedger Desktop._bookledger._tcp.local."
PROTOCOL_ID = "bookledger-mobile"


class MdnsServiceAdvertiser:
    """Advertise the active BookLedger HTTP endpoint through DNS-SD."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._zeroconf: Zeroconf | None = None
        self._info: ServiceInfo | None = None
        self._identity: tuple[int, tuple[str, ...]] | None = None

    def update(self, port: int, addresses: list[str]) -> None:
        usable_addresses: set[str] = set()
        for address in addresses:
            try:
                parsed = ipaddress.IPv4Address(address)
            except ipaddress.AddressValueError:
                continue
            if (
                parsed in ipaddress.IPv4Network("10.0.0.0/8")
                or parsed in ipaddress.IPv4Network("172.16.0.0/12")
                or parsed in ipaddress.IPv4Network("192.168.0.0/16")
            ):
                usable_addresses.add(str(parsed))
        usable = tuple(sorted(usable_addresses))
        if not usable or not 1 <= port <= 65535:
            self.stop()
            return

        identity = (port, usable)
        with self._lock:
            if self._identity == identity:
                return
            info = ServiceInfo(
                SERVICE_TYPE,
                SERVICE_NAME,
                addresses=[socket.inet_aton(address) for address in usable],
                port=port,
                properties={b"protocol": PROTOCOL_ID.encode("ascii"), b"version": b"1"},
                server="bookledger.local.",
            )
            if self._zeroconf is None:
                self._zeroconf = Zeroconf(interfaces=InterfaceChoice.All)
            if self._info is None:
                self._zeroconf.register_service(info)
            else:
                self._zeroconf.update_service(info)
            self._info = info
            self._identity = identity

    def stop(self) -> None:
        with self._lock:
            zeroconf = self._zeroconf
            info = self._info
            self._zeroconf = None
            self._info = None
            self._identity = None
        if zeroconf is None:
            return
        try:
            if info is not None:
                zeroconf.unregister_service(info)
        finally:
            zeroconf.close()
