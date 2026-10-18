from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

from bookledger.services.isbn import normalize_isbn
from bookledger.services.metadata import MetadataProvider, MetadataResult


_MAX_RESPONSE_BYTES = 2 * 1024 * 1024
_ALLOWED_HOSTS = {"booktopia.com.au", "www.booktopia.com.au"}
_VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}


class _BooktopiaRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        destination = urllib.parse.urlparse(urllib.parse.urljoin(request.full_url, new_url))
        if destination.scheme != "https" or (destination.hostname or "").casefold() not in _ALLOWED_HOSTS:
            raise ValueError("Booktopia redirected outside its website")
        return super().redirect_request(request, file_pointer, code, message, headers, new_url)


def _isbn_aliases(isbn: str) -> set[str]:
    aliases = {isbn}
    if len(isbn) == 10 and re.fullmatch(r"[0-9]{9}[0-9X]", isbn):
        prefix = "978" + isbn[:9]
        check = (10 - sum(int(digit) * (1 if index % 2 == 0 else 3) for index, digit in enumerate(prefix)) % 10) % 10
        aliases.add(prefix + str(check))
    elif len(isbn) == 13 and isbn.startswith("978") and isbn.isdigit():
        prefix = isbn[3:12]
        total = sum((10 - index) * (10 if digit == "X" else int(digit)) for index, digit in enumerate(prefix))
        check = "X" if total % 11 == 10 else str(total % 11)
        aliases.add(prefix + check)
    return aliases


class _BookPageParser(HTMLParser):
    """Read standard book/product metadata without executing page scripts."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.isbns: set[str] = set()
        self.descriptions: list[str] = []
        self.json_ld: list[object] = []
        self._script_parts: list[str] | None = None
        self._description_tags: list[str] = []
        self._description_parts: list[str] = []
        self._isbn_tags: list[str] = []
        self._isbn_parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        attributes = {key.casefold(): value or "" for key, value in attrs}
        if tag not in _VOID_TAGS:
            if self._description_tags:
                self._description_tags.append(tag)
            if self._isbn_tags:
                self._isbn_tags.append(tag)
        if tag == "meta":
            name = attributes.get("name", "").casefold()
            prop = attributes.get("property", "").casefold()
            itemprop = attributes.get("itemprop", "").casefold()
            value = attributes.get("content", "").strip()
            if value and (name in {"description", "og:description"} or prop == "og:description" or itemprop == "description"):
                self.descriptions.append(value)
            if itemprop in {"isbn", "isbn13", "gtin13"} and value:
                self.isbns.add(normalize_isbn(value))
        if tag == "script" and "ld+json" in attributes.get("type", "").casefold():
            self._script_parts = []
        itemprop = attributes.get("itemprop", "").casefold()
        if itemprop in {"isbn", "isbn13", "gtin13"}:
            value = attributes.get("content", "").strip()
            if value:
                self.isbns.add(normalize_isbn(value))
            elif tag not in _VOID_TAGS:
                self._isbn_tags = [tag]
                self._isbn_parts = []
        if itemprop == "description":
            value = attributes.get("content", "").strip()
            if value:
                self.descriptions.append(value)
            elif tag not in _VOID_TAGS:
                self._description_tags = [tag]
                self._description_parts = []

    def handle_endtag(self, tag):
        if tag == "script" and self._script_parts is not None:
            raw = "".join(self._script_parts).strip()
            try:
                self.json_ld.append(json.loads(raw))
            except (json.JSONDecodeError, TypeError):
                pass
            self._script_parts = None
        if self._description_tags:
            if tag == self._description_tags[-1]:
                self._description_tags.pop()
                if not self._description_tags:
                    text = " ".join("".join(self._description_parts).split())
                    if text:
                        self.descriptions.append(text)
                    self._description_parts = []
        if self._isbn_tags and tag == self._isbn_tags[-1]:
            self._isbn_tags.pop()
            if not self._isbn_tags:
                value = normalize_isbn("".join(self._isbn_parts).strip())
                if value:
                    self.isbns.add(value)
                self._isbn_parts = []

    def handle_data(self, data):
        if self._script_parts is not None:
            self._script_parts.append(data)
        if self._description_tags:
            self._description_parts.append(data)
        if self._isbn_tags:
            self._isbn_parts.append(data)


def _json_ld_metadata(nodes, requested_isbn: str):
    found_isbn = False
    descriptions: list[str] = []
    found_values: set[str] = set()
    aliases = _isbn_aliases(requested_isbn)

    def visit(node):
        nonlocal found_isbn
        if isinstance(node, dict):
            object_isbns = {
                normalize_isbn(str(node.get(key)))
                for key in ("isbn", "isbn13", "gtin13")
                if isinstance(node.get(key), (str, int))
            }
            found_values.update(value for value in object_isbns if value)
            if aliases.intersection(object_isbns):
                found_isbn = True
                description = node.get("description")
                if isinstance(description, str) and description.strip():
                    descriptions.append(description.strip())
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)

    for node in nodes:
        visit(node)
    return found_isbn, descriptions, found_values


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data):
        self.parts.append(data)


def _plain_text(value: str) -> str:
    parser = _TextExtractor()
    parser.feed(value)
    parser.close()
    return " ".join("".join(parser.parts).split())


def _url_matches_isbn(url: str, requested_isbn: str) -> bool:
    path = urllib.parse.urlparse(url).path
    match = re.search(r"/book/([0-9Xx-]{10,17})\.html/?$", path)
    return bool(match and normalize_isbn(match.group(1)) in _isbn_aliases(requested_isbn))


class BooktopiaProvider(MetadataProvider):
    """Best-effort Booktopia description enrichment with ISBN verification."""

    name = "Booktopia"

    def _open(self, request):
        opener = urllib.request.build_opener(_BooktopiaRedirectHandler())
        return opener.open(request, timeout=self.timeout)

    def lookup(self, isbn: str) -> MetadataResult:
        isbn = normalize_isbn(isbn) or ""
        requested_url = f"https://www.booktopia.com.au/book/{urllib.parse.quote(isbn)}.html/"
        request = urllib.request.Request(requested_url, headers={"User-Agent": "BookLedger/0.1", "Accept": "text/html"})
        try:
            with self._open(request) as response:
                final_url = response.geturl()
                parts = urllib.parse.urlparse(final_url)
                if parts.scheme != "https" or (parts.hostname or "").casefold() not in _ALLOWED_HOSTS:
                    return MetadataResult("Lookup failed", {}, self.name, "Unexpected redirect destination", "unexpected")
                content_type = response.headers.get_content_type()
                if content_type not in {"text/html", "application/xhtml+xml"}:
                    return MetadataResult("Lookup failed", {}, self.name, "Unexpected content type", "unexpected")
                raw = response.read(_MAX_RESPONSE_BYTES + 1)
                if len(raw) > _MAX_RESPONSE_BYTES:
                    return MetadataResult("Lookup failed", {}, self.name, "Product page exceeded response limit", "unexpected")
                charset = response.headers.get_content_charset() or "utf-8"
                html = raw.decode(charset, errors="replace")
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return MetadataResult("No data", {}, self.name, record_found=False)
            return self._failed(exc)
        except Exception as exc:
            return self._failed(exc)

        parser = _BookPageParser()
        try:
            parser.feed(html)
            parser.close()
        except Exception as exc:
            return self._failed(exc)

        structured_match, structured_descriptions, structured_isbns = _json_ld_metadata(parser.json_ld, isbn)
        url_match = _url_matches_isbn(final_url, isbn)
        page_match = structured_match or url_match
        aliases = _isbn_aliases(isbn)
        page_isbns = parser.isbns | structured_isbns
        if not page_match and not page_isbns:
            return MetadataResult("Lookup failed", {}, self.name, "Unexpected page without ISBN evidence", "unexpected")
        if not page_match or (page_isbns and not aliases.intersection(page_isbns)):
            return MetadataResult("No data", {}, self.name, record_found=False)

        description = next((_plain_text(value) for value in structured_descriptions if _plain_text(value)), None)
        if description is None:
            description = next((_plain_text(value) for value in parser.descriptions if _plain_text(value)), None)
        if not description:
            return MetadataResult("No data", {}, self.name, record_found=True)
        return MetadataResult("Retrieved", {"book_details": description}, self.name, record_found=True)
