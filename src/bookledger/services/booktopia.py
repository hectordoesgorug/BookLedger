from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

from bookledger.services.isbn import equivalent_isbn, isbn_check, normalize_isbn
from bookledger.services.metadata_contract import MetadataProvider, MetadataResult, provider_lookup


_MAX_RESPONSE_BYTES = 2 * 1024 * 1024
_MAX_PRODUCT_CANDIDATES = 2  # at most one ISBN-10 and one ISBN-13 URL
_ALLOWED_HOSTS = {"booktopia.com.au", "www.booktopia.com.au"}
_VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
_SUPPORTED_FORMATS = {"Paperback", "Hardcover", "Mass Market Paperback", "Board Book", "Other"}


class _BooktopiaRedirectHandler(urllib.request.HTTPRedirectHandler):
    def __init__(self, remaining_timeout=None):
        super().__init__()
        self.remaining_timeout = remaining_timeout

    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        destination = urllib.parse.urlparse(urllib.parse.urljoin(request.full_url, new_url))
        if destination.scheme != "https" or (destination.hostname or "").casefold() not in _ALLOWED_HOSTS:
            raise ValueError("Booktopia redirected outside its website")
        if self.remaining_timeout is not None:
            # urllib reuses the original request timeout for redirects. Shrink
            # that timeout to the provider's remaining budget before it follows.
            request.timeout = min(request.timeout, self.remaining_timeout())
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
        self.json_ld: list[object] = []
        self.links: list[str] = []
        self.elements: list[dict] = []
        self._element_stack: list[dict] = []
        self._script_parts: list[str] | None = None
        self._isbn_tags: list[str] = []
        self._isbn_parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        attributes = {key.casefold(): value or "" for key, value in attrs}
        element = {"tag": tag, "attrs": attributes, "content": []}
        self.elements.append(element)
        if self._element_stack:
            self._element_stack[-1]["content"].append(element)
        if tag not in _VOID_TAGS:
            self._element_stack.append(element)
        if tag not in _VOID_TAGS:
            if self._isbn_tags:
                self._isbn_tags.append(tag)
        if tag == "a" and attributes.get("href"):
            self.links.append(attributes["href"].strip())
        if tag == "meta":
            name = attributes.get("name", "").casefold()
            itemprop = attributes.get("itemprop", "").casefold()
            value = attributes.get("content", "").strip()
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

    def handle_endtag(self, tag):
        if tag == "script" and self._script_parts is not None:
            raw = "".join(self._script_parts).strip()
            try:
                self.json_ld.append(json.loads(raw))
            except (json.JSONDecodeError, TypeError):
                pass
            self._script_parts = None
        if self._isbn_tags and tag == self._isbn_tags[-1]:
            self._isbn_tags.pop()
            if not self._isbn_tags:
                value = normalize_isbn("".join(self._isbn_parts).strip())
                if value:
                    self.isbns.add(value)
                self._isbn_parts = []
        for index in range(len(self._element_stack) - 1, -1, -1):
            if self._element_stack[index]["tag"] == tag:
                del self._element_stack[index:]
                break

    def handle_data(self, data):
        if self._element_stack:
            self._element_stack[-1]["content"].append(data)
        if self._script_parts is not None:
            self._script_parts.append(data)
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


_BIBLIOGRAPHIC_CLAUSE = (
    r"includes?\s+(?:bibliographical references(?:\s*\([^)]*\))?(?:\s+and\s+index(?:es)?)?|"
    r"index(?:es)?(?:\s+and\s+bibliographical references(?:\s*\([^)]*\))?)?)"
)
_BIBLIOGRAPHIC_NOTE = re.compile(
    rf"^(?:(?:a\s+[^!?]+\s+book\.\s*)?(?:{_BIBLIOGRAPHIC_CLAUSE})(?:\.\s*{_BIBLIOGRAPHIC_CLAUSE})*\.?)$",
    re.IGNORECASE,
)
_STANDALONE_BOOK_NOTE = re.compile(r"^a\s+[^!?]+\s+book\.?$", re.IGNORECASE)
_DESCRIPTION_SECTION = re.compile(
    r"\b(?:about the author|author biography|industry reviews|shipping and returns|"
    r"frequently asked questions|what is .{1,100} about\?)\b",
    re.IGNORECASE,
)
_RETAIL_COPY = re.compile(
    r"\b(?:buy\b.{0,300}?\bfrom\s+booktopia\b|"
    r"get a discounted\b.{0,200}?\bfrom\s+(?:australia['’]s?\s+)?leading online bookstore\b|"
    r"australia['’]s?\s+leading online bookstore)\b",
    re.IGNORECASE,
)
_RECOMMENDATION = re.compile(
    r"\b(?:if you enjoyed\b.{0,250}?\byou might like\b|you may also like|you might also like|"
    r"readers also enjoyed)\b",
    re.IGNORECASE,
)
_UNAVAILABLE_PRODUCT = re.compile(
    r"\b(?:currently\s+)?unable to source (?:this|the) book\b|"
    r"\b(?:this\s+)?product is (?:currently\s+)?unavailable\b",
    re.IGNORECASE,
)
_BOOKTOPIA_BYLINE = re.compile(r"\bBy:\s*(.*?)\s+Write\s+A\s+Review\b", re.IGNORECASE)


def _clean_synopsis(value: str | None) -> str | None:
    """Reject known non-synopsis text and trim unrelated sections after a summary."""
    text = _plain_text(value or "")
    if not text:
        return None
    if _BIBLIOGRAPHIC_NOTE.fullmatch(text) or _STANDALONE_BOOK_NOTE.fullmatch(text):
        return None

    cutoffs = [match.start() for pattern in (_DESCRIPTION_SECTION, _RETAIL_COPY, _RECOMMENDATION)
               if (match := pattern.search(text))]
    if cutoffs:
        text = text[:min(cutoffs)].strip()
    if not text or _BIBLIOGRAPHIC_NOTE.fullmatch(text) or _STANDALONE_BOOK_NOTE.fullmatch(text):
        return None
    if _RETAIL_COPY.search(text):
        return None
    return text


def _element_text(element: dict) -> str:
    if element["tag"] in {"script", "style", "noscript", "template"}:
        return ""
    parts = []
    for child in element["content"]:
        parts.append(_element_text(child) if isinstance(child, dict) else child)
    return " ".join(" ".join(parts).split())


def _description_panel_text(parser: _BookPageParser) -> list[str]:
    """Extract text only when the Description tab explicitly identifies its panel."""
    descriptions = []
    for tab in parser.elements:
        attrs = tab["attrs"]
        tab_id = attrs.get("id", "")
        if tab_id.casefold() != "pdp-tab-description":
            continue
        targets = set(attrs.get("aria-controls", "").split())
        for key in ("href", "data-target", "data-bs-target"):
            target = attrs.get(key, "").strip()
            if target.startswith("#"):
                targets.add(target[1:])
        for panel in parser.elements:
            panel_attrs = panel["attrs"]
            panel_id = panel_attrs.get("id", "")
            labelled_by = set(panel_attrs.get("aria-labelledby", "").split())
            if (panel_id and panel_id in targets) or tab_id in labelled_by:
                text = _element_text(panel)
                if text:
                    descriptions.append(text)
    return descriptions


def _product_is_unavailable(parser: _BookPageParser, matching_nodes: list[dict]) -> bool:
    page = next((element for element in parser.elements if element["tag"] == "html"), None)
    if page and _UNAVAILABLE_PRODUCT.search(_element_text(page)):
        return True
    for node in matching_nodes:
        offers = node.get("offers") or []
        offers = offers if isinstance(offers, list) else [offers]
        for offer in offers:
            if not isinstance(offer, dict):
                continue
            availability = _schema_text(offer.get("availability")) or ""
            state = urllib.parse.unquote(availability).rstrip("/").rsplit("/", 1)[-1].casefold()
            if state in {"outofstock", "discontinued", "soldout"}:
                return True
    return False


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
        if is_book(node):
            description = _schema_text(node.get("description"))
            if description:
                descriptions.append(description)
    return values, descriptions


def _metadata_from_page(parser: _BookPageParser) -> dict:
    """Read title and author from standard page semantics when JSON-LD omits them."""
    values = {}
    for element in parser.elements:
        attrs = element["attrs"]
        tag = element["tag"]
        if "title" not in values and tag == "h1":
            title = _schema_text(_element_text(element))
            if title:
                values["title"] = title
        if "author" not in values and tag == "meta":
            name = attrs.get("name", "").casefold()
            itemprop = attrs.get("itemprop", "").casefold()
            if name == "author" or itemprop == "author":
                author = _schema_text(attrs.get("content"))
                if author:
                    values["author"] = author
        if "author" not in values and attrs.get("itemprop", "").casefold() == "author":
            author = _schema_text(_element_text(element) or attrs.get("content"))
            if author:
                values["author"] = author
        if len(values) == 2:
            break
    if "author" not in values:
        bylines = []
        for element in parser.elements:
            text = _element_text(element)
            match = _BOOKTOPIA_BYLINE.search(text)
            if match and (author := _schema_text(match.group(1))):
                bylines.append((len(text), author))
        if bylines:
            # The smallest containing element avoids pulling in unrelated page text.
            values["author"] = min(bylines, key=lambda candidate: candidate[0])[1]
    return values


_PRODUCT_DETAIL_LABELS = (
    "ISBN-10", "ISBN", "Series", "Published", "Format", "Language",
    "Number of Pages", "Audience", "For Ages", "For Grades", "Publisher",
    "Country of Publication", "Dimensions (cm)", "Weight (kg)",
)


def _metadata_from_product_details(parser: _BookPageParser) -> dict:
    """Read a few exact Product Details labels from visible, verified page text.

    This intentionally uses labels rather than a Booktopia CSS selector: the
    adapter only has the returned HTML and must not depend on tab implementation.
    JSON-LD remains authoritative because callers merge these values only when
    the structured field is absent.
    """
    page = next((element for element in parser.elements if element["tag"] == "html"), None)
    if not page:
        return {}
    text = " ".join(_element_text(page).split())
    labels = "|".join(re.escape(label) for label in _PRODUCT_DETAIL_LABELS)
    result = {}

    def labelled_value(label: str) -> str | None:
        match = re.search(
            rf"(?<![\w]){re.escape(label)}\s*:\s*(.*?)(?=\s+(?:{labels})\s*:|$)",
            text,
            re.IGNORECASE,
        )
        value = " ".join(match.group(1).split()).strip(" .;,") if match else ""
        return value or None

    published = labelled_value("Published")
    if year := _schema_year(published):
        result["publication_year"] = year
    if publisher := labelled_value("Publisher"):
        result["publisher"] = publisher
    if page_count := labelled_value("Number of Pages"):
        match = re.fullmatch(r"\s*(\d{1,5})(?:\s+pages?)?\s*", page_count, re.IGNORECASE)
        if match and (number := _schema_page_count(match.group(1))):
            result["page_count"] = number
    if book_format := _schema_format(labelled_value("Format")):
        result["format"] = book_format
    return result


def _url_matches_isbn(url: str, requested_isbn: str) -> bool:
    path = urllib.parse.urlparse(url).path
    # Booktopia's direct ISBN route is only a redirect entry point. A product
    # page must resolve to a slugged canonical URL before its URL can verify it.
    match = re.search(r"/(?:[^/]+/)+book/([0-9Xx-]{10,17})\.html/?$", path)
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
        opener = urllib.request.build_opener(_BooktopiaRedirectHandler(self._request_timeout))
        return opener.open(request, timeout=self._request_timeout())

    def _read_page(self, url: str) -> tuple[str, str, urllib.error.HTTPError | None]:
        request = urllib.request.Request(url, headers={"User-Agent": "BookLedger/0.1", "Accept": "text/html"})
        try:
            response = self._open(request)
        except urllib.error.HTTPError as exc:
            # urllib exposes non-2xx response bodies as HTTPError objects. Keep
            # the error so callers can report it unless the body proves to be
            # a usable, ISBN-verified product page.
            response = exc
            http_error = exc
        else:
            http_error = None

        final_url = url
        with response:
            try:
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
            except Exception:
                if http_error is not None:
                    return final_url, "", http_error
                raise
        return final_url, html, http_error

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
        if not url_match:
            return MetadataResult(
                "No data", {}, self.name,
                "The response URL is not a canonical product URL for the requested ISBN",
                "unverified", record_found=False,
            )
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
        for key, value in _metadata_from_page(parser).items():
            if values.get(key) in (None, ""):
                values[key] = value
        for key, value in _metadata_from_product_details(parser).items():
            if values.get(key) in (None, ""):
                values[key] = value
        unavailable = _product_is_unavailable(parser, matching_nodes)
        description_candidates = _description_panel_text(parser) + structured_descriptions
        description = next(
            (cleaned for candidate in description_candidates if (cleaned := _clean_synopsis(candidate))),
            None,
        )
        if description:
            values["book_details"] = description
        if not values:
            return MetadataResult(
                "No data", {}, self.name,
                failure_kind="unavailable" if unavailable else None, record_found=True,
            )
        return MetadataResult(
            "Retrieved", values, self.name,
            failure_kind="unavailable" if unavailable else None, record_found=True,
        )

    def _verified_http_error_page_result(
        self, final_url: str, html: str, isbn: str
    ) -> MetadataResult | None:
        """Accept an error response only when it contains usable canonical product data."""
        if not html or not _url_matches_isbn(final_url, isbn):
            return None
        try:
            result = self._product_result(final_url, html, isbn)
        except Exception:
            return None
        if result.record_found is True and result.values:
            return result
        return None

    def _lookup_direct_isbn_page(self, isbn: str) -> MetadataResult:
        direct_url = f"https://booktopia.com.au/book/{isbn}.html/"
        try:
            final_url, html, http_error = self._read_page(direct_url)
        except Exception as exc:
            return self._failed(exc)

        if http_error is not None:
            return self._verified_http_error_page_result(final_url, html, isbn) or self._failed(http_error)
        if not _url_matches_isbn(final_url, isbn):
            return MetadataResult(
                "No data", {}, self.name,
                "The direct ISBN URL did not resolve to a canonical product page",
                "unverified", record_found=False,
            )
        try:
            return self._product_result(final_url, html, isbn)
        except Exception as exc:
            return self._failed(exc)

    def _retry_direct_after_search_error(self, isbn: str, search_error: Exception) -> MetadataResult:
        result = self._lookup_direct_isbn_page(isbn)
        if result.record_found is True and result.values:
            return result
        if result.failure_kind == "timeout":
            return result
        return self._failed(search_error)

    @provider_lookup
    def lookup(self, isbn: str) -> MetadataResult:
        isbn = normalize_isbn(isbn) or ""
        valid, _message = isbn_check(isbn)
        if not isbn or not valid:
            return MetadataResult("No data", {}, self.name, "The submitted ISBN is invalid", "unverified", record_found=False)

        search_url = "https://www.booktopia.com.au/search.ep?" + urllib.parse.urlencode({"keywords": isbn})
        try:
            search_final_url, search_html, search_error = self._read_page(search_url)
        except urllib.error.HTTPError as exc:
            return self._retry_direct_after_search_error(isbn, exc)
        except Exception as exc:
            return self._failed(exc)

        if search_error is not None:
            result = self._verified_http_error_page_result(search_final_url, search_html, isbn)
            if result is not None:
                return result
            return self._retry_direct_after_search_error(isbn, search_error)

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
                final_url, html, http_error = self._read_page(candidate)
                if http_error is not None:
                    result = self._verified_http_error_page_result(final_url, html, isbn)
                    if result is None:
                        failures.append(self._failed(http_error))
                        continue
                else:
                    result = self._product_result(final_url, html, isbn)
            except urllib.error.HTTPError as exc:
                failures.append(self._failed(exc))
                continue
            except Exception as exc:
                if self._failed(exc).failure_kind == "timeout":
                    return self._failed(exc)
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
