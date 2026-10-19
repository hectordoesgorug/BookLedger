from __future__ import annotations

import urllib.parse

from bookledger.services.isbn import equivalent_isbn, normalize_isbn
from bookledger.services.metadata_contract import MetadataProvider, MetadataResult, provider_lookup


class OpenLibraryProvider(MetadataProvider):
    """Primary ISBN metadata provider using Open Library's Books API."""

    name = "Open Library"

    @provider_lookup
    def lookup(self, isbn: str) -> MetadataResult:
        isbn = normalize_isbn(isbn) or ""
        lookup_isbns = tuple(dict.fromkeys(value for value in (isbn, equivalent_isbn(isbn)) if value))
        keys = tuple(f"ISBN:{value}" for value in lookup_isbns)
        query = urllib.parse.urlencode({"bibkeys": ",".join(keys), "format": "json", "jscmd": "data"})
        try:
            payload = self._request_json(f"https://openlibrary.org/api/books?{query}")
        except Exception as exc:
            return self._failed(exc)
        if not isinstance(payload, dict):
            return self._failed(ValueError("Open Library returned an unexpected response shape"))
        info = None
        saw_unverified_record = False
        for candidate in keys:
            candidate_info = payload.get(candidate)
            if candidate_info is None:
                continue
            if not isinstance(candidate_info, dict):
                return self._failed(ValueError("Open Library returned an unexpected response shape"))
            identifiers = candidate_info.get("identifiers") or {}
            returned = {
                normalize_isbn(value)
                for values in identifiers.values()
                for value in (values if isinstance(values, list) else [values])
            }
            if not returned or returned.intersection(lookup_isbns):
                info = candidate_info
                break
            saw_unverified_record = True
        if info is None:
            if saw_unverified_record:
                return MetadataResult(
                    "No data", {}, self.name,
                    "Open Library returned a record with identifiers that did not match the entered ISBN.",
                    "unverified", record_found=False,
                )
            return MetadataResult("No data", {}, self.name, record_found=False)

        authors = info.get("authors") or []
        publishers = info.get("publishers") or []
        subjects = info.get("subjects") or []
        published = str(info.get("publish_date") or "")
        values = {
            "title": info.get("title"),
            "author": ", ".join(author.get("name", "") for author in authors if author.get("name")) or None,
            "isbn": isbn,
            "genre": next((subject.get("name") for subject in subjects if subject.get("name")), None),
            # Edition notes and descriptions are bibliographic notes, not synopsis copy.
            "book_details": None,
            "publisher": ", ".join(publisher.get("name", "") for publisher in publishers if publisher.get("name")) or None,
            "publication_year": int(published[:4]) if published[:4].isdigit() else None,
            "edition": info.get("edition_name"),
            "page_count": info.get("number_of_pages"),
            "srp": None,
        }
        has_metadata = any(value for key, value in values.items() if key != "isbn")
        return MetadataResult(
            "Retrieved" if has_metadata else "No data",
            values if has_metadata else {}, self.name, record_found=True,
        )
