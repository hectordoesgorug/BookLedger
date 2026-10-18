from __future__ import annotations

import json
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Callable, Iterable

from bookledger.services.isbn import normalize_isbn


_SMALL_TITLE_WORDS = {"a", "an", "and", "as", "at", "but", "by", "for", "from", "in", "into", "nor", "of", "on", "onto", "or", "over", "the", "to", "up", "with"}
_TITLE_ACRONYMS = {"api", "dna", "isbn", "nasa", "usa", "uk", "un", "us", "wwii"}


def normalize_provider_title(title: str | None) -> str | None:
    """Apply readable title case to provider titles while preserving common acronyms."""
    if not title or not str(title).strip():
        return title

    def normalize_word(word: str, first: bool, after_colon: bool) -> str:
        parts = re.split(r"([-'’])", word)
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
        # Punctuation stays attached to each word; a colon starts a new subtitle.
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
    failure_kind: str | None = None  # timeout, network, provider


def _failure_kind(exc: Exception) -> str:
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
    if isinstance(exc, (ConnectionError, socket.gaierror)):
        return "network"
    return "provider"


class MetadataProvider:
    """Provider interface; implementations return normalized bibliographic fields."""

    name = "Provider"
    timeout = 10

    def lookup(self, isbn: str) -> MetadataResult:
        raise NotImplementedError

    def _request_json(self, url: str) -> dict:
        request = urllib.request.Request(url, headers={"User-Agent": "BookLedger/0.1"})
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def _failed(self, exc: Exception) -> MetadataResult:
        return MetadataResult("Lookup failed", {}, self.name, str(exc), _failure_kind(exc))


class OpenLibraryProvider(MetadataProvider):
    """Primary ISBN metadata provider using Open Library's Books API."""

    name = "Open Library"

    def lookup(self, isbn: str) -> MetadataResult:
        isbn = normalize_isbn(isbn) or ""
        key = f"ISBN:{isbn}"
        query = urllib.parse.urlencode({"bibkeys": key, "format": "json", "jscmd": "data"})
        try:
            payload = self._request_json(f"https://openlibrary.org/api/books?{query}")
        except Exception as exc:
            return self._failed(exc)
        info = payload.get(key)
        if not isinstance(info, dict):
            return MetadataResult("No data", {}, self.name)

        identifiers = info.get("identifiers") or {}
        returned = {normalize_isbn(value) for values in identifiers.values() for value in (values if isinstance(values, list) else [values])}
        if returned and isbn not in returned:
            return MetadataResult("No data", {}, self.name)

        authors = info.get("authors") or []
        publishers = info.get("publishers") or []
        subjects = info.get("subjects") or []
        published = str(info.get("publish_date") or "")
        values = {
            "title": info.get("title"),
            "author": ", ".join(author.get("name", "") for author in authors if author.get("name")) or None,
            "isbn": isbn,
            "genre": next((subject.get("name") for subject in subjects if subject.get("name")), None),
            "book_details": info.get("notes"),
            "publisher": ", ".join(publisher.get("name", "") for publisher in publishers if publisher.get("name")) or None,
            "publication_year": int(published[:4]) if published[:4].isdigit() else None,
            "edition": info.get("edition_name"),
            "page_count": info.get("number_of_pages"),
            "srp": None,
        }
        has_metadata = any(value for key, value in values.items() if key != "isbn")
        return MetadataResult("Retrieved" if has_metadata else "No data", values if has_metadata else {}, self.name)


class GoogleBooksProvider(MetadataProvider):
    """Optional fallback provider with an independent per-request timeout."""

    name = "Google Books"

    def __init__(self, api_key: str | None = None):
        self.api_key = (api_key or "").strip()

    def lookup(self, isbn: str) -> MetadataResult:
        isbn = normalize_isbn(isbn) or ""
        params = {"q": f"isbn:{isbn}", "maxResults": 5}
        if self.api_key:
            params["key"] = self.api_key
        query = urllib.parse.urlencode(params)
        try:
            payload = self._request_json(f"https://www.googleapis.com/books/v1/volumes?{query}")
        except Exception as exc:
            return self._failed(exc)
        items = payload.get("items") or []
        info = None
        for item in items:
            candidate = item.get("volumeInfo") or {}
            identifiers = candidate.get("industryIdentifiers") or []
            if any(normalize_isbn(identifier.get("identifier")) == isbn for identifier in identifiers):
                info = candidate
                break
        if info is None:
            return MetadataResult("No data", {}, self.name)

        identifiers = info.get("industryIdentifiers") or []
        returned_isbn = next((x.get("identifier") for x in identifiers if normalize_isbn(x.get("identifier")) == isbn), isbn)
        published = str(info.get("publishedDate") or "")
        values = {
            "title": info.get("title"),
            "author": ", ".join(info.get("authors") or []) or None,
            "isbn": returned_isbn,
            "genre": (info.get("categories") or [None])[0],
            "book_details": info.get("description"),
            "publisher": info.get("publisher"),
            "publication_year": int(published[:4]) if published[:4].isdigit() else None,
            "page_count": info.get("pageCount"),
            "srp": None,
        }
        has_metadata = any(value for key, value in values.items() if key != "isbn")
        return MetadataResult("Retrieved" if has_metadata else "No data", values if has_metadata else {}, self.name)


class MetadataLookupService:
    """Try replaceable providers in order, giving each its own request timeout."""

    def __init__(self, providers: Iterable[MetadataProvider] | None = None):
        self.providers = tuple(providers) if providers is not None else (OpenLibraryProvider(), GoogleBooksProvider())

    def lookup(self, isbn: str, *, on_status: Callable[[str], None] | None = None) -> MetadataResult:
        failures: list[MetadataResult] = []
        primary_failure: MetadataResult | None = None
        combined: dict = {}
        sources: list[str] = []
        supported = ("title", "author", "genre", "book_details", "publisher", "publication_year", "edition", "page_count", "srp")
        for index, provider in enumerate(self.providers):
            missing = [key for key in supported if combined.get(key) in (None, "")]
            if combined and not missing:
                break
            if on_status:
                on_status(f"Searching ISBN: {provider.name}")
                on_status("Fetching Data…")
            try:
                result = provider.lookup(isbn)
            except Exception as exc:
                result = MetadataResult("Lookup failed", {}, provider.name, str(exc), _failure_kind(exc))
            values = {key: value for key, value in result.values.items() if value not in (None, "")}
            if "title" in values:
                values["title"] = normalize_provider_title(str(values["title"]))
            if values:
                if result.source:
                    sources.append(result.source)
                for key, value in values.items():
                    if combined.get(key) in (None, ""):
                        combined[key] = value
            if result.status == "Lookup failed":
                failures.append(result)
                if index == 0:
                    primary_failure = result

        if combined:
            if primary_failure is not None and len(sources) == 1 and sources[0] != primary_failure.source:
                # A matching fallback result is a successful lookup even when the
                # primary provider was unavailable; retain that failure for diagnostics.
                return MetadataResult(
                    "Retrieved", combined, " + ".join(dict.fromkeys(sources)),
                    primary_failure.error, primary_failure.failure_kind,
                )
            if failures and len(sources) <= 1:
                failure = failures[0]
                return MetadataResult("Lookup failed", combined, ", ".join(sources) or failure.source, failure.error, failure.failure_kind)
            return MetadataResult("Retrieved", combined, " + ".join(dict.fromkeys(sources)))
        if failures:
            # The first provider is primary; its specific error is the most useful
            # explanation when the fallback also fails or returns no matching record.
            return failures[0]
        source = self.providers[-1].name if self.providers else None
        return MetadataResult("No data", {}, source)
