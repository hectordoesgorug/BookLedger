from __future__ import annotations

import urllib.parse

from bookledger.services.isbn import equivalent_isbn, normalize_isbn
from bookledger.services.metadata_contract import MetadataProvider, MetadataResult, failure_kind, provider_lookup


class GoogleBooksProvider(MetadataProvider):
    """Optional fallback provider with an independent five-second lookup budget."""

    name = "Google Books"

    def __init__(self, api_key: str | None = None):
        super().__init__()
        self.api_key = (api_key or "").strip()

    @provider_lookup
    def lookup(self, isbn: str) -> MetadataResult:
        isbn = normalize_isbn(isbn) or ""
        lookup_isbns = tuple(dict.fromkeys(value for value in (isbn, equivalent_isbn(isbn)) if value))
        failures: list[Exception] = []
        saw_unverified_result = False
        matched_record_found = False
        matched_values: dict = {}
        queries = tuple(dict.fromkeys((isbn, *(f"isbn:{value}" for value in lookup_isbns))))
        for query_term in queries:
            params = {"q": query_term, "maxResults": 5}
            if self.api_key:
                params["key"] = self.api_key
            query = urllib.parse.urlencode(params)
            try:
                payload = self._request_json(f"https://www.googleapis.com/books/v1/volumes?{query}")
            except Exception as exc:
                if failure_kind(exc) == "timeout":
                    return self._failed(exc)
                failures.append(exc)
                continue
            if not isinstance(payload, dict):
                failures.append(ValueError("Google Books returned an unexpected response shape"))
                continue
            total_items = payload.get("totalItems")
            if total_items is not None and (not isinstance(total_items, int) or isinstance(total_items, bool) or total_items < 0):
                failures.append(ValueError("Google Books returned an unexpected response shape"))
                continue
            items = payload.get("items") or []
            if not isinstance(items, list):
                failures.append(ValueError("Google Books returned an unexpected response shape"))
                continue
            if total_items and not items:
                failures.append(ValueError("Google Books returned an incomplete response"))
                continue
            for item in items:
                if not isinstance(item, dict) or not isinstance(item.get("volumeInfo"), dict):
                    failures.append(ValueError("Google Books returned an unexpected response shape"))
                    continue
                candidate = item["volumeInfo"]
                identifiers = candidate.get("industryIdentifiers") or []
                if not isinstance(identifiers, list):
                    failures.append(ValueError("Google Books returned an unexpected response shape"))
                    continue
                if any(not isinstance(identifier, dict) for identifier in identifiers):
                    failures.append(ValueError("Google Books returned an unexpected response shape"))
                    continue
                returned_isbns = {
                    normalize_isbn(identifier.get("identifier")) for identifier in identifiers
                }
                if returned_isbns.intersection(lookup_isbns):
                    matched_record_found = True
                    candidate_result = self._result_from_volume_info(candidate, lookup_isbns)
                    for field, value in candidate_result.values.items():
                        if matched_values.get(field) in (None, "") and value not in (None, ""):
                            matched_values[field] = value
                else:
                    saw_unverified_result = True
            # Keep searching variants when a verified result is sparse, so a later
            # result can supply fields such as Book Details.
            if matched_values.get("book_details") not in (None, ""):
                break

        if matched_values:
            return MetadataResult("Retrieved", matched_values, self.name, record_found=True)
        if matched_record_found:
            return MetadataResult("No data", {}, self.name, record_found=True)
        if failures:
            return self._failed(failures[0])
        if saw_unverified_result:
            return MetadataResult(
                "No data", {}, self.name,
                "Google Books returned volumes without an identifier matching the entered ISBN.",
                "unverified", record_found=False,
            )
        return MetadataResult("No data", {}, self.name, record_found=False)

    def _result_from_volume_info(self, info: dict, lookup_isbns: tuple[str, ...]) -> MetadataResult:
        identifiers = info.get("industryIdentifiers") or []
        returned_isbn = next((
            item.get("identifier") for item in identifiers
            if isinstance(item, dict) and normalize_isbn(item.get("identifier")) in lookup_isbns
        ), lookup_isbns[0])
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
        return MetadataResult(
            "Retrieved" if has_metadata else "No data",
            values if has_metadata else {}, self.name, record_found=True,
        )
