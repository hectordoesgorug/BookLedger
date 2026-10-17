from __future__ import annotations
import json
import urllib.parse
import urllib.request
from dataclasses import dataclass


@dataclass
class MetadataResult:
    status: str  # Retrieved, No data, Lookup failed, Manual entry
    values: dict
    source: str | None = None
    error: str | None = None


class MetadataProvider:
    """Provider interface; implementations return normalized fields."""
    name = "provider"

    def lookup(self, isbn: str) -> MetadataResult:
        raise NotImplementedError


class GoogleBooksProvider(MetadataProvider):
    """Optional online provider. The app remains usable when this provider fails."""
    name = "Google Books"

    def lookup(self, isbn: str) -> MetadataResult:
        query = urllib.parse.urlencode({"q": f"isbn:{isbn}", "maxResults": 5})
        request = urllib.request.Request(
            f"https://www.googleapis.com/books/v1/volumes?{query}",
            headers={"User-Agent": "BookLedger/0.1"},
        )
        try:
            with urllib.request.urlopen(request, timeout=8) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            return MetadataResult("Lookup failed", {}, self.name, str(exc))
        items = payload.get("items") or []
        if not items:
            return MetadataResult("No data", {}, self.name)
        info = items[0].get("volumeInfo") or {}
        identifiers = info.get("industryIdentifiers") or []
        returned_isbn = next((x.get("identifier") for x in identifiers if x.get("type") in {"ISBN_13", "ISBN_10"}), None)
        values = {
            "title": info.get("title"),
            "author": ", ".join(info.get("authors") or []) or None,
            "isbn": returned_isbn or isbn,
            "genre": (info.get("categories") or [None])[0],
            "book_details": info.get("description"),
            "publisher": info.get("publisher"),
            "publication_year": int(info["publishedDate"][:4]) if info.get("publishedDate", "")[:4].isdigit() else None,
            "page_count": info.get("pageCount"),
            "srp": None,
        }
        return MetadataResult("Retrieved" if any(values.values()) else "No data", values, self.name)
