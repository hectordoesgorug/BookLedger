from __future__ import annotations

import math
import urllib.error
import urllib.parse

from bookledger.services.isbn import equivalent_isbn, isbn_check, normalize_isbn
from bookledger.services.metadata_contract import MetadataProvider, MetadataResult, failure_kind, provider_lookup


class BigbookProvider(MetadataProvider):
    """ISBN metadata adapter for Bigbook API."""

    name = "Bigbook"

    def __init__(self, api_key: str | None = None):
        super().__init__()
        self.api_key = (api_key or "").strip()

    @provider_lookup
    def lookup(self, isbn: str) -> MetadataResult:
        if not self.api_key:
            return MetadataResult("Lookup failed", {}, self.name, "Bigbook API key is required.", "authentication")
        requested = normalize_isbn(isbn) or ""
        valid, _message = isbn_check(requested)
        if not valid:
            return MetadataResult("No data", {}, self.name, record_found=False)
        isbn13 = requested if len(requested) == 13 else equivalent_isbn(requested)
        if not isbn13 or len(isbn13) != 13:
            return MetadataResult("No data", {}, self.name, record_found=False)
        expected_isbns = {value for value in (isbn13, equivalent_isbn(isbn13)) if value}
        url = "https://api.bigbookapi.com/search-books?" + urllib.parse.urlencode({"isbn": isbn13})
        try:
            payload = self._request_json_with_headers(url, {"x-api-key": self.api_key})
        except urllib.error.HTTPError as exc:
            return self._http_failure(exc)
        except Exception as exc:
            return self._failed(exc)

        candidates = self._candidate_books(payload)
        if candidates is None:
            return self._failed(ValueError("Bigbook returned an unexpected search response"))
        if not candidates:
            return MetadataResult("No data", {}, self.name, record_found=False)

        saw_unverified = False
        failures: list[Exception] = []
        for candidate in candidates[:10]:
            candidate_id = candidate.get("id")
            if not isinstance(candidate_id, (str, int)) or isinstance(candidate_id, bool):
                saw_unverified = True
                continue
            detail_url = f"https://api.bigbookapi.com/{urllib.parse.quote(str(candidate_id), safe='')}"
            try:
                details = self._request_json_with_headers(detail_url, {"x-api-key": self.api_key})
            except Exception as exc:
                if failure_kind(exc) == "timeout":
                    return self._failed(exc)
                if isinstance(exc, urllib.error.HTTPError):
                    failure = self._http_failure(exc)
                    if failure is not None:
                        return failure
                failures.append(exc)
                continue
            if not isinstance(details, dict):
                failures.append(ValueError("Bigbook returned an unexpected book response"))
                continue
            if not self._matches_isbn(details, expected_isbns):
                saw_unverified = True
                continue
            values = self._map_details(details, isbn13)
            if any(value not in (None, "") for key, value in values.items() if key != "isbn"):
                return MetadataResult("Retrieved", values, self.name, record_found=True)
            return MetadataResult("No data", {}, self.name, record_found=True)

        if failures:
            return self._failed(failures[0])
        if saw_unverified or candidates:
            return MetadataResult(
                "No data", {}, self.name,
                "Bigbook results could not be verified against the entered ISBN.",
                "unverified", record_found=False,
            )
        return MetadataResult("No data", {}, self.name, record_found=False)

    def _http_failure(self, exc: urllib.error.HTTPError) -> MetadataResult:
        classifications = {
            401: ("authentication", "Bigbook rejected the API key."),
            403: ("authorization", "Bigbook denied access to the request."),
            402: ("quota", "Bigbook daily API quota is exhausted."),
            429: ("rate_limit", "Bigbook rate limit was reached."),
        }
        classification = classifications.get(exc.code)
        if classification is None:
            return self._failed(exc)
        kind, message = classification
        return MetadataResult("Lookup failed", {}, self.name, message, kind)

    @staticmethod
    def _candidate_books(payload):
        if not isinstance(payload, dict):
            return None
        books = payload.get("books")
        if books is None:
            return []
        if not isinstance(books, list):
            return None
        flattened = []
        for group in books:
            entries = group if isinstance(group, list) else [group]
            for item in entries:
                if not isinstance(item, dict):
                    return None
                flattened.append(item)
        return flattened

    @staticmethod
    def _matches_isbn(details: dict, expected_isbns: set[str]) -> bool:
        identifiers = details.get("identifiers")
        if not isinstance(identifiers, dict):
            return False
        returned = {
            normalized
            for field in ("isbn_10", "isbn_13")
            if (normalized := normalize_isbn(identifiers.get(field)))
        }
        return bool(returned.intersection(expected_isbns))

    @staticmethod
    def _year(value):
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if isinstance(value, float) and not math.isfinite(value):
                return None
            year = int(value)
            return year if 1000 <= year <= 9999 else None
        text = str(value or "")
        year_text = text[:4]
        return int(year_text) if year_text.isdigit() and 1000 <= int(year_text) <= 9999 else None

    @staticmethod
    def _page_count(value):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        return int(value) if math.isfinite(value) and value > 0 and float(value).is_integer() else None

    @classmethod
    def _map_details(cls, details: dict, isbn13: str) -> dict:
        authors = details.get("authors") or []
        if not isinstance(authors, list):
            authors = []
        author_names = [item.get("name", "").strip() for item in authors if isinstance(item, dict) and isinstance(item.get("name"), str)]
        title = details.get("title")
        description = details.get("description")
        return {
            "title": title.strip() if isinstance(title, str) and title.strip() else None,
            "author": ", ".join(name for name in author_names if name) or None,
            "isbn": isbn13,
            "book_details": description.strip() if isinstance(description, str) and description.strip() else None,
            "publication_year": cls._year(details.get("publish_date")),
            "page_count": cls._page_count(details.get("number_of_pages")),
        }

