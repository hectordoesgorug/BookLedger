from __future__ import annotations

import json
import re
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from functools import wraps


_SMALL_TITLE_WORDS = {"a", "an", "and", "as", "at", "but", "by", "for", "from", "in", "into", "nor", "of", "on", "onto", "or", "over", "the", "to", "up", "with"}
_TITLE_ACRONYMS = {"api", "dna", "isbn", "nasa", "usa", "uk", "un", "us", "wwii"}


def normalize_provider_title(title: str | None) -> str | None:
    """Apply readable title case to provider titles while preserving common acronyms."""
    if not title or not str(title).strip():
        return title

    def normalize_word(word: str, first: bool, after_colon: bool) -> str:
        parts = re.split(r"([-’'])", word)
        output = []
        for part in parts:
            if part in {"-", "'", "’"}:
                output.append(part)
                continue
            leading = part[: len(part) - len(part.lstrip("([{\"“‘"))]
            trailing = part[len(part.rstrip(").,!?;:]}\"”’")) :]
            core = part[len(leading) : len(part) - len(trailing) if trailing else len(part)]
            key = core.casefold()
            if key in _TITLE_ACRONYMS:
                output.append(leading + key.upper() + trailing)
            elif len(core) > 1 and any(c.isupper() for c in core[1:]) and any(c.islower() for c in core):
                output.append(part)
            elif key in _SMALL_TITLE_WORDS and not first and not after_colon:
                output.append(leading + key + trailing)
            else:
                output.append(leading + (core[:1].upper() + core[1:].lower()) + trailing)
        return "".join(output)

    words = str(title).split()
    result = []
    after_colon = False
    for index, word in enumerate(words):
        normalized = normalize_word(word, index == 0 or after_colon or index == len(words) - 1, after_colon)
        result.append(normalized)
        after_colon = ":" in word
    return " ".join(result)


@dataclass
class MetadataResult:
    status: str  # Retrieved, No data, Lookup failed, Manual entry
    values: dict
    source: str | None = None
    error: str | None = None
    failure_kind: str | None = None  # timeout, network, provider, unexpected, unverified, unavailable
    record_found: bool | None = None
    provider_statuses: dict[str, str] = field(default_factory=dict)
    partial: bool = False
    supported_fields: frozenset[str] = field(default_factory=frozenset)
    missing_fields: frozenset[str] = field(default_factory=frozenset)
    unsupported_fields: frozenset[str] = field(default_factory=frozenset)
    provider_durations: dict[str, float] = field(default_factory=dict)
    duration_seconds: float = 0.0


def failure_kind(exc: Exception) -> str:
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return "timeout"
    if isinstance(exc, urllib.error.HTTPError):
        return "provider"
    if isinstance(exc, urllib.error.URLError):
        reason = exc.reason
        if isinstance(reason, (TimeoutError, socket.timeout)):
            return "timeout"
        if isinstance(reason, (ConnectionError, socket.gaierror, OSError)):
            return "network"
        return "provider"
    if isinstance(exc, (ConnectionError, socket.gaierror, OSError)):
        return "network"
    if isinstance(exc, (json.JSONDecodeError, UnicodeDecodeError, TypeError, ValueError, KeyError, AttributeError)):
        return "unexpected"
    return "unexpected"


class MetadataProvider:
    """Common adapter contract with a five-second per-lookup request budget."""

    name = "Provider"
    timeout = 5

    def __init__(self):
        self._lookup_deadline: float | None = None

    def _request_timeout(self) -> float:
        if self._lookup_deadline is None:
            return self.timeout
        remaining = self._lookup_deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(f"{self.name} lookup exceeded its {self.timeout}-second budget")
        return remaining

    def lookup(self, isbn: str) -> MetadataResult:
        raise NotImplementedError

    def _request_json(self, url: str) -> dict:
        request = urllib.request.Request(url, headers={"User-Agent": "BookLedger/0.1"})
        with urllib.request.urlopen(request, timeout=self._request_timeout()) as response:
            return json.loads(response.read().decode("utf-8"))

    def _failed(self, exc: Exception) -> MetadataResult:
        return MetadataResult("Lookup failed", {}, self.name, str(exc), failure_kind(exc))


def provider_lookup(method):
    """Apply one wall-clock budget and measure all requests in an adapter lookup."""
    @wraps(method)
    def wrapped(self, isbn):
        started = time.monotonic()
        previous_deadline = self._lookup_deadline
        self._lookup_deadline = started + self.timeout
        try:
            result = method(self, isbn)
        finally:
            self._lookup_deadline = previous_deadline
        if isinstance(result, MetadataResult):
            elapsed = time.monotonic() - started
            if elapsed > self.timeout and result.failure_kind != "timeout":
                result = self._failed(TimeoutError(
                    f"{self.name} lookup exceeded its {self.timeout}-second budget"
                ))
            result.duration_seconds = elapsed
        return result
    return wrapped
