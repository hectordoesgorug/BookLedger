from __future__ import annotations

import html
import json
import re
import urllib.parse
import urllib.request

from bookledger.services.isbn import equivalent_isbn, isbn_check, normalize_isbn
from bookledger.services.metadata_contract import MetadataProvider, MetadataResult, failure_kind, provider_lookup


ADVANCED_SEARCH_URL = "https://archive.org/advancedsearch.php"
ITEM_METADATA_URL = "https://archive.org/metadata/{}"
DEFAULT_RESULT_LIMIT = 10
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_VERIFIED_CANDIDATES = 3
_ADMIN_TITLE = re.compile(
    r"^(?:archive(?:\.org)?|internet archive|metadata|collection|collections|"
    r"community text|community audio|item metadata)(?:\b|\s*[:/-])",
    re.IGNORECASE,
)
_YEAR = re.compile(r"\b(?:1[5-9]\d{2}|20\d{2}|21\d{2})\b")
_ISBN_TEXT = re.compile(r"(?<![0-9X])(?:\d[\s-]*){9,12}[\dX](?![0-9X])", re.IGNORECASE)
_HTML_TAG = re.compile(r"<[^>]*>")


def _first_text(value) -> str | None:
    if isinstance(value, str):
        text = " ".join(html.unescape(value).split())
        return text or None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, dict):
        for key in ("value", "text", "name", "description"):
            text = _first_text(value.get(key))
            if text:
                return text
    if isinstance(value, list):
        for item in value:
            text = _first_text(item)
            if text:
                return text
    return None


def _description(value) -> str | None:
    if isinstance(value, list):
        pieces = list(dict.fromkeys(text for item in value if (text := _first_text(item))))
        text = " ".join(pieces) or None
    else:
        text = _first_text(value)
    if not text:
        return None
    text = " ".join(_HTML_TAG.sub(" ", text).split())
    if len(text) < 80:
        return None
    lowered = text.casefold()
    if any(phrase in lowered for phrase in (
        "internet archive", "borrow this book", "terms of use", "download options",
    )):
        return None
    return text[:5000]


def _creator(value) -> str | None:
    text = _first_text(value)
    if not text:
        return None
    # IA creator can contain roles and many contributors. Keep the first listed
    # creator instead of presenting a catalog's full contributor set as authors.
    return re.split(r"\s*[;|]\s*", text, maxsplit=1)[0].strip() or None


def _year(value) -> int | None:
    text = _first_text(value)
    match = _YEAR.search(text or "")
    return int(match.group(0)) if match else None


def _normalized_title(value) -> str | None:
    text = _first_text(value)
    if not text:
        return None
    text = " ".join(text.split())
    if _ADMIN_TITLE.match(text) or text.casefold() in {"book", "books", "untitled"}:
        return None
    return text


def _candidate_values(document: dict) -> dict:
    return {
        "title": _normalized_title(document.get("title")),
        "author": _creator(document.get("creator")),
        "publisher": _first_text(document.get("publisher")),
        "publication_year": _year(document.get("year")),
        "edition": _first_text(document.get("edition")),
        "book_details": _description(document.get("description")),
    }


def _candidate_score(values: dict) -> int:
    if not values.get("title"):
        return -1
    # Search is already constrained to the requested ISBN. Prefer coherent,
    # edition-like records with useful bibliographic fields over sparse hits.
    return (
        100
        + (12 if values.get("author") else 0)
        + (5 if values.get("publisher") else 0)
        + (4 if values.get("publication_year") else 0)
        + (3 if values.get("edition") else 0)
        + (8 if values.get("book_details") else 0)
    )


def _isbn_values(metadata: dict) -> set[str]:
    found: set[str] = set()

    def visit(value):
        if isinstance(value, (list, tuple, set)):
            for item in value:
                visit(item)
            return
        if isinstance(value, dict):
            for item in value.values():
                visit(item)
            return
        if not isinstance(value, (str, int)):
            return
        text = str(value)
        candidates = [text, *_ISBN_TEXT.findall(text)]
        for candidate in candidates:
            normalized = normalize_isbn(candidate)
            if normalized and isbn_check(normalized)[0]:
                found.add(normalized)

    for key, value in metadata.items():
        if "isbn" in re.sub(r"[^a-z]", "", str(key).casefold()):
            visit(value)
    return found


class ArchiveOrgProvider(MetadataProvider):
    """Archive.org Advanced Search adapter with bounded, conservative selection."""

    name = "Archive.org"
    timeout = 5.0

    def __init__(self, *, result_limit: int = DEFAULT_RESULT_LIMIT):
        super().__init__()
        self.result_limit = max(1, min(int(result_limit), 10))

    def _request_json(self, url: str) -> dict:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "BookLedger/0.1", "Accept": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=self._request_timeout()) as response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
        if len(body) > MAX_RESPONSE_BYTES:
            raise ValueError("Archive.org response exceeded the 2 MiB safety limit")
        payload = json.loads(body.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Archive.org returned an unexpected JSON response")
        return payload

    def _search(self, isbn: str) -> list[dict]:
        params = [
            ("q", f"isbn:{isbn}"),
            ("fl[]", "identifier"),
            ("fl[]", "title"),
            ("fl[]", "creator"),
            ("fl[]", "publisher"),
            ("fl[]", "year"),
            ("fl[]", "edition"),
            ("fl[]", "description"),
            ("rows", str(self.result_limit)),
            ("output", "json"),
        ]
        payload = self._request_json(f"{ADVANCED_SEARCH_URL}?{urllib.parse.urlencode(params)}")
        response = payload.get("response")
        if not isinstance(response, dict) or not isinstance(response.get("docs"), list):
            raise ValueError("Archive.org returned an unexpected search response shape")
        docs = response["docs"]
        if any(not isinstance(document, dict) for document in docs):
            raise ValueError("Archive.org returned an unexpected search document")
        return docs

    def _item_isbns(self, identifier: str) -> set[str]:
        url = ITEM_METADATA_URL.format(urllib.parse.quote(identifier, safe=""))
        payload = self._request_json(url)
        metadata = payload.get("metadata")
        if metadata is None:
            return set()
        if not isinstance(metadata, dict):
            raise ValueError("Archive.org returned unexpected item metadata")
        return _isbn_values(metadata)

    def _candidates(self, documents: list[dict]) -> list[dict]:
        # Duplicate search rows for the same IA identifier are redundant.
        # Distinct identifiers remain separate even when their title/creator
        # match, since they may represent different editions or ISBNs.
        unique: dict[str, dict] = {}
        for index, document in enumerate(documents):
            values = _candidate_values(document)
            score = _candidate_score(values)
            identifier = _first_text(document.get("identifier"))
            if score < 0 or not identifier:
                continue
            candidate = {"identifier": identifier, "values": values, "score": score, "index": index}
            key = identifier
            current = unique.get(key)
            if current is None or (score, -index) > (current["score"], -current["index"]):
                unique[key] = candidate
        return sorted(unique.values(), key=lambda item: (-item["score"], item["index"]))

    @provider_lookup
    def lookup(self, isbn: str) -> MetadataResult:
        requested = normalize_isbn(isbn) or ""
        if not isbn_check(requested)[0]:
            return MetadataResult("No data", {}, self.name, record_found=False)
        equivalent = equivalent_isbn(requested)
        accepted_isbns = {requested, equivalent} if equivalent else {requested}
        try:
            candidates = self._candidates(self._search(requested))
        except Exception as exc:
            return self._failed(exc)
        if not candidates:
            return MetadataResult("No data", {}, self.name, record_found=False)

        selected = candidates[0]
        verified = None
        if len(candidates) > 1:
            checked = candidates[:MAX_VERIFIED_CANDIDATES]
            for candidate in checked:
                try:
                    isbns = self._item_isbns(candidate["identifier"])
                except Exception as exc:
                    return self._failed(exc)
                if isbns.intersection(accepted_isbns):
                    verified = candidate
                    break
                # A present ISBN set that conflicts with the request is strong
                # evidence against this record. Empty sets remain unverified.
            if verified is None:
                return MetadataResult(
                    "No data", {}, self.name,
                    "Archive.org returned ambiguous records without a verified ISBN match.",
                    "unverified", record_found=False,
                )
            selected = verified

        values = {key: value for key, value in selected["values"].items() if value not in (None, "")}
        if not values:
            return MetadataResult("No data", {}, self.name, record_found=True)
        # Keep the IA identifier available in the result source for diagnostics;
        # do not add a database field for it.
        source = f"{self.name} ({selected['identifier']})"
        return MetadataResult("Retrieved", values, source, record_found=True)
