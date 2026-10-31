from __future__ import annotations

import json
import urllib.error
import urllib.request

from bookledger.services.isbn import equivalent_isbn, isbn_check, normalize_isbn
from bookledger.services.metadata_contract import MetadataProvider, MetadataResult, provider_lookup


HARDCOVER_ENDPOINT = "https://api.hardcover.app/v1/graphql"


class HardcoverProvider(MetadataProvider):
    """Isolated GraphQL adapter for Hardcover's beta API."""

    name = "Hardcover"

    def __init__(self, api_token: str | None = None):
        super().__init__()
        self.api_token = (api_token or "").strip()

    @provider_lookup
    def lookup(self, isbn: str) -> MetadataResult:
        if not self.api_token:
            return MetadataResult("Lookup failed", {}, self.name, "Hardcover API token is required.", "authentication")
        requested = normalize_isbn(isbn) or ""
        valid, _message = isbn_check(requested)
        if not valid:
            return MetadataResult("No data", {}, self.name, record_found=False)
        isbn13 = requested if len(requested) == 13 else equivalent_isbn(requested)
        isbn10 = requested if len(requested) == 10 else equivalent_isbn(requested)
        query = """
        query EditionByISBN($isbn10: String!, $isbn13: String!) {
          byIsbn13: editions(where: {isbn_13: {_eq: $isbn13}}, limit: 5) {
            id title subtitle isbn_10 isbn_13 pages release_date release_year
            edition_format edition_information description
            publisher { name }
            book {
              title description release_date release_year pages author_names genres
            }
          }
          byIsbn10: editions(where: {isbn_10: {_eq: $isbn10}}, limit: 5) {
            id title subtitle isbn_10 isbn_13 pages release_date release_year
            edition_format edition_information description
            publisher { name }
            book {
              title description release_date release_year pages author_names genres
            }
          }
        }
        """
        request = urllib.request.Request(
            HARDCOVER_ENDPOINT,
            data=json.dumps({"query": query, "variables": {"isbn10": isbn10 or "", "isbn13": isbn13 or ""}}).encode("utf-8"),
            headers={
                "User-Agent": "BookLedger/0.1 (ISBN metadata lookup)",
                "Content-Type": "application/json",
                "authorization": self.api_token,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._request_timeout()) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code in {401, 403, 404, 429, 500}:
                kind = "authentication" if exc.code == 401 else "authorization" if exc.code == 403 else "rate_limit" if exc.code == 429 else "provider"
                label = {401: "invalid or expired token", 403: "access denied", 404: "endpoint not found", 429: "rate limit was reached", 500: "service error"}[exc.code]
                return MetadataResult("Lookup failed", {}, self.name, f"Hardcover {label} (HTTP {exc.code}).", kind)
            return self._failed(exc)
        except Exception as exc:
            return self._failed(exc)

        if not isinstance(payload, dict):
            return self._failed(ValueError("Hardcover returned an invalid GraphQL response"))
        errors = payload.get("errors")
        if errors:
            # GraphQL can return HTTP 200 with authentication, authorization, or
            # resolver failures. Keep the actual message out of diagnostics.
            if not isinstance(errors, list):
                return self._failed(ValueError("Hardcover returned invalid GraphQL errors"))
            message = " ".join(str(item.get("message", "")) for item in errors if isinstance(item, dict)).casefold()
            if any(term in message for term in ("unauthorized", "invalid token", "expired token")):
                kind, description = "authentication", "invalid or expired token"
            elif any(term in message for term in ("forbidden", "permission", "access denied")):
                kind, description = "authorization", "access denied"
            elif "throttl" in message or "rate limit" in message:
                kind, description = "rate_limit", "rate limit was reached"
            else:
                kind, description = "provider", "GraphQL request failed"
            return MetadataResult("Lookup failed", {}, self.name, f"Hardcover {description}.", kind)
        data = payload.get("data")
        if not isinstance(data, dict):
            return self._failed(ValueError("Hardcover returned an invalid GraphQL response"))
        editions = []
        for key in ("byIsbn13", "byIsbn10"):
            values = data.get(key)
            if values is None:
                continue
            if not isinstance(values, list) or any(not isinstance(item, dict) for item in values):
                return self._failed(ValueError("Hardcover returned malformed editions"))
            editions.extend(values)
        if not editions:
            return MetadataResult("No data", {}, self.name, record_found=False)
        expected = {value for value in (isbn13, isbn10) if value}
        for edition in editions:
            if not self._matches_isbn(edition, expected):
                continue
            values = self._map_edition(edition, isbn13 or requested)
            if any(value not in (None, "") for key, value in values.items() if key != "isbn"):
                return MetadataResult("Retrieved", values, self.name, record_found=True)
            return MetadataResult("No data", {}, self.name, record_found=True)
        return MetadataResult(
            "No data", {}, self.name,
            "Hardcover returned editions that could not be verified against the entered ISBN.",
            "unverified", record_found=False,
        )

    @staticmethod
    def _matches_isbn(edition: dict, expected: set[str]) -> bool:
        returned = {value for field in ("isbn_10", "isbn_13") if (value := normalize_isbn(edition.get(field)))}
        return bool(returned.intersection(expected))

    @staticmethod
    def _year(*values):
        for value in values:
            if isinstance(value, int) and not isinstance(value, bool) and 1000 <= value <= 9999:
                return value
            text = str(value or "")
            if len(text) >= 4 and text[:4].isdigit():
                year = int(text[:4])
                if 1000 <= year <= 9999:
                    return year
        return None

    @staticmethod
    def _first_text(*values):
        return next((value.strip() for value in values if isinstance(value, str) and value.strip()), None)

    @classmethod
    def _map_edition(cls, edition: dict, requested_isbn: str) -> dict:
        book = edition.get("book") if isinstance(edition.get("book"), dict) else {}
        publisher = edition.get("publisher") if isinstance(edition.get("publisher"), dict) else {}
        names = book.get("author_names")
        authors = [name.strip() for name in names if isinstance(name, str)] if isinstance(names, list) else []
        genres = book.get("genres")
        title = cls._first_text(book.get("title"), edition.get("title"), edition.get("subtitle"))
        description = cls._first_text(edition.get("description"), book.get("description"))
        edition_text = cls._first_text(edition.get("edition_information"), edition.get("edition_format"), edition.get("physical_format"))
        return {
            "title": title,
            "author": ", ".join(name for name in authors if name) or None,
            "isbn": cls._first_text(edition.get("isbn_13"), edition.get("isbn_10"), requested_isbn),
            "genre": next((value.strip() for value in genres if isinstance(value, str) and value.strip()), None) if isinstance(genres, list) else None,
            "publisher": cls._first_text(publisher.get("name")),
            "publication_year": cls._year(edition.get("release_year"), edition.get("release_date"), book.get("release_year"), book.get("release_date")),
            "edition": edition_text,
            "page_count": next((value for value in (edition.get("pages"), book.get("pages")) if isinstance(value, int) and not isinstance(value, bool) and value > 0), None),
            "book_details": description,
        }
