from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

from bookledger.services.isbn import equivalent_isbn, isbn_check, normalize_isbn
from bookledger.services.metadata import MetadataProvider, MetadataResult


_MAX_RESPONSE_BYTES = 2 * 1024 * 1024
_MAX_PRODUCT_CANDIDATES = 2  # at most one ISBN-10 and one ISBN-13 URL
_ALLOWED_HOSTS = {"booktopia.com.au", "www.booktopia.com.au"}
_VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
_SUPPORTED_FORMATS = {"Paperback", "Hardcover", "Mass Market Paperback", "Board Book", "Other"}


class _BooktopiaRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        destination = urllib.parse.urlparse(urllib.parse.urljoin(request.full_url, new_url))
        if destination.scheme != "https" or (destination.hostname or "").casefold() not in _ALLOWED_HOSTS:
            raise ValueError("Booktopia redirected outside its website")
        return super().redirect_request(request, file_pointer, code, message, headers, new_url)


def _isbn_aliases(isbn: str) -> set[str]:
    aliases = {isbn}
    alias = equivalent_isbn(isbn)
    if alias:
        aliases.add(alias)
    return aliases


class _BookPageParser(HTMLParser):
    """Read standard book/product metadata without executing page scripts."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.isbns: set[str] = set()
        self.descriptions: list[str] = []
        self.json_ld: list[object] = []
        self.links: list[str] = []
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
        if tag == "a" and attributes.get("href"):
            self.links.append(attributes["href"].strip())
        if tag == "meta":
            name = attributes.get("name", "").casefold()
            prop = attributes.get("property", "").casefold()
            itemprop = attributes.get("itemprop", "").casefold()
            value = attributes.get("content", "").strip()
            if value and (name in {"description", "og:description"} or prop == "og:description" or itemprop == "description"):
                self.descriptions.append(value)
            if itemprop in {"isbn", "isbn10", "isbn13", "gtin13"} and value:
                normalized = normalize_isbn(value)
                if normalized:
                    self.isbns.add(normalized)
        if tag == "script" and "ld+json" in attributes.get("type", "").casefold():
            self._script_parts = []
        itemprop = attributes.get("itemprop", "").casefold()
        if itemprop in {"isbn", "isbn10", "isbn13", "gtin13"}:
            value = attributes.get("content", "").strip()
            if value:
                normalized = normalize_isbn(value)
                if normalized:
                    self.isbns.add(normalized)
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
        if self._description_tags and tag == self._description_tags[-1]:
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


def _schema_text(value) -> str | None:
    if isinstance(value, str):
        text = _plain_text(value)
        return text or None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, list):
        parts = [part for item in value if (part := _schema_text(item))]
        return "; ".join(dict.fromkeys(parts)) or None
    if isinstance(value, dict):
        for key in ("name", "alternateName", "value"):
            text = _schema_text(value.get(key))
            if text:
                return text
    return None


def _schema_year(value) -> int | None:
    text = _schema_text(value)
    match = re.search(r"(?<!\d)(\d{4})(?!\d)", text or "")
    return int(match.group(1)) if match else None


def _schema_page_count(value) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    if isinstance(value, str) and re.fullmatch(r"\s*\d+\s*", value):
        number = int(value)
        return number if number > 0 else None
    return None


def _schema_format(value) -> str | None:
    text = _schema_text(value)
    if not text and isinstance(value, dict):
        text = _schema_text(value.get("@id") or value.get("url"))
    if not text:
        return None
    label = urllib.parse.urlparse(text).path.rstrip("/").rsplit("/", 1)[-1]
    label = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", label).replace("_", " ").replace("-", " ")
    normalized = " ".join(label.split()).casefold()
    formats = {
        "paperback": "Paperback",
        "softcover": "Paperback",
        "hardcover": "Hardcover",
        "hardback": "Hardcover",
        "mass market paperback": "Mass Market Paperback",
        "board book": "Board Book",
        "other": "Other",
    }
    result = formats.get(normalized)
    return result if result in _SUPPORTED_FORMATS else None


def _json_ld_metadata(nodes, requested_isbn: str):
    matches: list[dict] = []
    found_values: set[str] = set()
    aliases = _isbn_aliases(requested_isbn)
    visited: set[int] = set()

    def visit(node):
        if isinstance(node, dict):
            object_isbns = {
                normalize_isbn(str(node.get(key)))
                for key in ("isbn", "isbn10", "isbn13", "gtin13")
                if isinstance(node.get(key), (str, int))
            }
            found_values.update(value for value in object_isbns if value)
            if aliases.intersection(object_isbns) and id(node) not in visited:
                matches.append(node)
                visited.add(id(node))
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)

    for node in nodes:
        visit(node)
    return matches, found_values


def _metadata_from_jsonld(matching_nodes) -> tuple[dict, list[str]]:
    def is_book(node):
        types = node.get("@type", ())
        types = [types] if isinstance(types, str) else types
        return any(str(value).rsplit("/", 1)[-1].casefold() == "book" for value in types)

    ordered = sorted(matching_nodes, key=lambda node: not is_book(node))
    values = {}
    descriptions = []
    field_map = {
        "title": ("name",),
        "author": ("author",),
        "publisher": ("publisher",),
        "publication_year": ("datePublished",),
        "edition": ("bookEdition", "edition"),
        "page_count": ("numberOfPages",),
        "format": ("bookFormat",),
    }
    for node in ordered:
        for key, candidates in field_map.items():
            if values.get(key) not in (None, ""):
                continue
            for candidate in candidates:
                raw = node.get(candidate)
                if key == "publication_year":
                    value = _schema_year(raw)
                elif key == "page_count":
                    value = _schema_page_count(raw)
                elif key == "format":
                    value = _schema_format(raw)
                else:
                    value = _schema_text(raw)
                if value not in (None, ""):
                    values[key] = value
                    break
        description = _schema_text(node.get("description"))
        if description:
            descriptions.append(description)
    return values, descriptions


def _url_matches_isbn(url: str, requested_isbn: str) -> bool:
    path = urllib.parse.urlparse(url).path
    match = re.search(r"/book/([0-9Xx-]{10,17})\.html/?$", path)
    return bool(match and normalize_isbn(match.group(1)) in _isbn_aliases(requested_isbn))


def _candidate_product_urls(links: list[str], base_url: str, requested_isbn: str) -> list[str]:
    candidates = []
    seen = set()
    for link in links:
        url = urllib.parse.urljoin(base_url, link)
        parts = urllib.parse.urlparse(url)
        if parts.scheme != "https" or (parts.hostname or "").casefold() not in _ALLOWED_HOSTS:
            continue
        if not _url_matches_isbn(url, requested_isbn):
            continue
        canonical = urllib.parse.urlunparse(("https", parts.netloc.casefold(), parts.path, "", "", ""))
        if canonical not in seen:
            seen.add(canonical)
            candidates.append(canonical)
        if len(candidates) >= _MAX_PRODUCT_CANDIDATES:
            break
    return candidates


class BooktopiaProvider(MetadataProvider):
    """Best-effort Booktopia HTML enrichment with bounded, ISBN-verified requests."""

    name = "Booktopia"

    def _open(self, request):
        opener = urllib.request.build_opener(_BooktopiaRedirectHandler())
        return opener.open(request, timeout=self.timeout)

    def _read_page(self, url: str) -> tuple[str, str]:
        request = urllib.request.Request(url, headers={"User-Agent": "BookLedger/0.1", "Accept": "text/html"})
        with self._open(request) as response:
            final_url = response.geturl()
            parts = urllib.parse.urlparse(final_url)
            if parts.scheme != "https" or (parts.hostname or "").casefold() not in _ALLOWED_HOSTS:
                raise ValueError("Booktopia redirected outside its website")
            content_type = response.headers.get_content_type()
            if content_type not in {"text/html", "application/xhtml+xml"}:
                raise ValueError("Booktopia returned an unexpected content type")
            raw = response.read(_MAX_RESPONSE_BYTES + 1)
            if len(raw) > _MAX_RESPONSE_BYTES:
                raise ValueError("Booktopia page exceeded response limit")
            charset = response.headers.get_content_charset() or "utf-8"
            html = raw.decode(charset, errors="replace")
        return final_url, html

    @staticmethod
    def _parse_page(html: str) -> _BookPageParser:
        parser = _BookPageParser()
        parser.feed(html)
        parser.close()
        return parser

    def _product_result(self, final_url: str, html: str, isbn: str) -> MetadataResult:
        parser = self._parse_page(html)
        matching_nodes, structured_isbns = _json_ld_metadata(parser.json_ld, isbn)
        structured_match = bool(matching_nodes)
        url_match = _url_matches_isbn(final_url, isbn)
        aliases = _isbn_aliases(isbn)
        page_isbns = parser.isbns | structured_isbns
        if not page_isbns:
            if url_match:
                return MetadataResult(
                    "No data", {}, self.name, "The product page did not expose an ISBN to verify", "unverified", record_found=False
                )
            return MetadataResult("Lookup failed", {}, self.name, "Unexpected page without ISBN evidence", "unexpected")
        if not (structured_match or url_match) or not aliases.intersection(page_isbns):
            return MetadataResult("No data", {}, self.name, record_found=False)

        values, structured_descriptions = _metadata_from_jsonld(matching_nodes)
        description = next((value for value in structured_descriptions if _plain_text(value)), None)
        if description is None:
            description = next((value for value in parser.descriptions if _plain_text(value)), None)
        if description:
            values["book_details"] = _plain_text(description)
        if not values:
            return MetadataResult("No data", {}, self.name, record_found=True)
        return MetadataResult("Retrieved", values, self.name, record_found=True)

    def lookup(self, isbn: str) -> MetadataResult:
        isbn = normalize_isbn(isbn) or ""
        valid, _message = isbn_check(isbn)
        if not isbn or not valid:
            return MetadataResult("No data", {}, self.name, "The submitted ISBN is invalid", "unverified", record_found=False)

        search_url = "https://www.booktopia.com.au/search.ep?" + urllib.parse.urlencode({"keywords": isbn})
        try:
            search_final_url, search_html = self._read_page(search_url)
        except urllib.error.HTTPError as exc:
            return self._failed(exc)
        except Exception as exc:
            return self._failed(exc)

        if _url_matches_isbn(search_final_url, isbn):
            try:
                return self._product_result(search_final_url, search_html, isbn)
            except Exception as exc:
                return self._failed(exc)

        try:
            search_parser = self._parse_page(search_html)
        except Exception as exc:
            return self._failed(exc)
        candidates = _candidate_product_urls(search_parser.links, search_final_url, isbn)
        if not candidates:
            return MetadataResult(
                "No data", {}, self.name, "Search response did not expose a verifiable matching product link",
                "unverified", record_found=False,
            )

        not_found = False
        unverified: MetadataResult | None = None
        matched_without_values: MetadataResult | None = None
        failures: list[MetadataResult] = []
        for candidate in candidates:
            try:
                final_url, html = self._read_page(candidate)
                result = self._product_result(final_url, html, isbn)
            except urllib.error.HTTPError as exc:
                failures.append(self._failed(exc))
                continue
            except Exception as exc:
                failures.append(self._failed(exc))
                continue
            if result.values:
                return result
            if result.record_found is True:
                matched_without_values = result
            elif result.failure_kind == "unverified":
                unverified = result
            elif result.record_found is False:
                not_found = True
            elif result.status == "Lookup failed":
                failures.append(result)

        if matched_without_values is not None:
            return matched_without_values
        if failures:
            return failures[0]
        if not_found:
            return MetadataResult("No data", {}, self.name, record_found=False)
        if unverified is not None:
            return unverified
        return MetadataResult("No data", {}, self.name, record_found=False)
