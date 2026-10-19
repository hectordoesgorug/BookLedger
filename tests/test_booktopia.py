from email.message import Message
from io import BytesIO
from pathlib import Path

import urllib.error
import pytest
from urllib.request import Request

from bookledger.services.booktopia import BooktopiaProvider, _BooktopiaRedirectHandler
from bookledger.services.metadata import MetadataLookupService, MetadataResult


FIXTURES = Path(__file__).parent / "fixtures" / "booktopia"
ISBN = "9780140449136"
PRODUCT_URL = "https://www.booktopia.com.au/crime-and-punishment-fyodor-dostoyevsky/book/9780140449136.html"
SEARCH_URL = "https://www.booktopia.com.au/search.ep?keywords=9780140449136"
STRENGTH_ISBN = "9781923058507"
STRENGTH_URL = "https://www.booktopia.com.au/the-strength-of-the-few-james-islington/book/9781923058507.html"
UNAVAILABLE_ISBN = "9780306406157"
UNAVAILABLE_URL = "https://www.booktopia.com.au/synthetic-unavailable-book/book/9780306406157.html"
NIGHTFALL_ISBN = "9780553290998"
NIGHTFALL_SEARCH_URL = "https://www.booktopia.com.au/search.ep?keywords=9780553290998"
NIGHTFALL_DIRECT_URL = "https://booktopia.com.au/book/9780553290998.html/"
NIGHTFALL_CANONICAL_URL = "https://www.booktopia.com.au/nightfall-isaac-asimov/book/9780553290998.html"


class FakeResponse:
    def __init__(self, body, url=PRODUCT_URL, content_type="text/html; charset=utf-8"):
        self.body = body
        self.url = url
        self.headers = Message()
        self.headers["Content-Type"] = content_type

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def geturl(self):
        return self.url

    def read(self, size=-1):
        return self.body if size < 0 else self.body[:size]


def _fixture(name):
    return (FIXTURES / name).read_bytes()


def _http_error(url, body=None, status=404):
    headers = Message()
    if body is not None:
        headers["Content-Type"] = "text/html; charset=utf-8"
    return urllib.error.HTTPError(
        url, status, "Not Found", headers,
        BytesIO(body) if body is not None else None,
    )


def _mock_response(monkeypatch, response):
    return _mock_responses(monkeypatch, response)


def _mock_responses(monkeypatch, *responses):
    called = []
    pending = list(responses)

    class FakeOpener:
        def open(self, request, *, timeout):
            called.append((request.full_url, timeout))
            response = pending.pop(0)
            if isinstance(response, BaseException):
                raise response
            return response

    monkeypatch.setattr("bookledger.services.booktopia.urllib.request.build_opener", lambda *_handlers: FakeOpener())
    return called


def test_booktopia_follows_redirect_and_extracts_matching_book_description(monkeypatch):
    provider = BooktopiaProvider()
    called = _mock_response(monkeypatch, FakeResponse(_fixture("matching_product.html")))

    result = provider.lookup(ISBN)

    assert [url for url, _timeout in called] == [SEARCH_URL]
    assert 0 < called[0][1] <= 5
    assert result.status == "Retrieved"
    assert result.record_found is True
    assert result.values == {
        "title": "Sample Novel",
        "book_details": "Product description with nested markup.",
    }


def test_booktopia_uses_verified_canonical_product_body_from_http_redirect(monkeypatch):
    provider = BooktopiaProvider()
    error_response = _http_error(PRODUCT_URL, _fixture("matching_product.html"))
    called = _mock_response(monkeypatch, error_response)

    result = provider.lookup(ISBN)

    assert [url for url, _timeout in called] == [SEARCH_URL]
    assert 0 < called[0][1] <= 5
    assert result.status == "Retrieved"
    assert result.record_found is True
    assert result.values["book_details"] == "Product description with nested markup."


def test_booktopia_search_http_failure_falls_back_to_direct_isbn_redirect(monkeypatch):
    provider = BooktopiaProvider()
    called = _mock_responses(
        monkeypatch,
        _http_error(NIGHTFALL_SEARCH_URL, b"<!doctype html><title>Page Not Found</title>"),
        FakeResponse(_fixture("nightfall_unavailable_synthetic.html"), NIGHTFALL_CANONICAL_URL),
    )

    result = provider.lookup(NIGHTFALL_ISBN)

    assert [url for url, _timeout in called] == [NIGHTFALL_SEARCH_URL, NIGHTFALL_DIRECT_URL]
    assert all(0 < timeout <= 5 for _url, timeout in called)
    assert result.status == "Retrieved"
    assert result.record_found is True
    assert result.failure_kind == "unavailable"
    assert result.values == {
        "title": "Nightfall",
        "author": "Isaac Asimov",
        "book_details": "Synthetic synopsis used only to test the direct-ISBN fallback.",
    }


def test_booktopia_semantic_page_metadata_flows_through_orchestration(monkeypatch):
    provider = BooktopiaProvider()
    _mock_response(monkeypatch, FakeResponse(
        _fixture("nightfall_semantic_metadata_synthetic.html"), NIGHTFALL_CANONICAL_URL
    ))

    result = MetadataLookupService((provider,)).lookup(NIGHTFALL_ISBN)

    assert result.status == "Retrieved"
    assert result.source == "Booktopia"
    assert result.values == {
        "title": "Nightfall",
        "author": "Isaac Asimov",
        "publication_year": 1991,
        "book_details": "A synthetic synopsis matching the reported listing fields.",
    }
    assert result.provider_statuses["Booktopia"] == "Product unavailable"


def test_booktopia_reads_nightfall_product_details_fields_and_propagates_them(monkeypatch):
    provider = BooktopiaProvider()
    _mock_response(monkeypatch, FakeResponse(
        _fixture("nightfall_product_details_synthetic.html"), NIGHTFALL_CANONICAL_URL
    ))

    result = MetadataLookupService((provider,)).lookup(NIGHTFALL_ISBN)

    assert result.status == "Retrieved"
    assert result.values == {
        "title": "Nightfall",
        "author": "Isaac Asimov",
        "publication_year": 1991,
        "book_details": "A synthetic synopsis for the Product Details fallback test.",
        "publisher": "BANTAM TRADE",
        "page_count": 352,
        "format": "Paperback",
    }


def test_booktopia_jsonld_page_count_keeps_precedence_over_product_details(monkeypatch):
    provider = BooktopiaProvider()
    html = _fixture("nightfall_product_details_synthetic.html").decode("utf-8")
    html = html.replace('"datePublished": "1991-08-01",', '"datePublished": "1991-08-01",\n        "numberOfPages": 360,')
    _mock_response(monkeypatch, FakeResponse(html.encode("utf-8"), NIGHTFALL_CANONICAL_URL))

    result = provider.lookup(NIGHTFALL_ISBN)

    assert result.values["page_count"] == 360


def test_booktopia_product_details_do_not_overwrite_prior_provider_page_count(monkeypatch):
    class OpenLibraryStub:
        name = "Open Library"

        def lookup(self, _isbn):
            return MetadataResult("Retrieved", {
                "title": "Nightfall", "author": "Isaac Asimov", "page_count": 341,
            }, self.name)

    booktopia = BooktopiaProvider()
    _mock_response(monkeypatch, FakeResponse(
        _fixture("nightfall_product_details_synthetic.html"), NIGHTFALL_CANONICAL_URL
    ))

    result = MetadataLookupService((OpenLibraryStub(), booktopia)).lookup(NIGHTFALL_ISBN)

    assert result.values["page_count"] == 341
    assert result.values["publisher"] == "BANTAM TRADE"
    assert result.values["format"] == "Paperback"


def test_booktopia_strength_of_the_few_byline_author_flows_through_orchestration(monkeypatch):
    provider = BooktopiaProvider()
    _mock_response(monkeypatch, FakeResponse(
        _fixture("strength_of_the_few_byline_synthetic.html"), STRENGTH_URL
    ))

    result = MetadataLookupService((provider,)).lookup(STRENGTH_ISBN)

    assert result.status == "Retrieved"
    assert result.values["title"] == "The Strength of the Few"
    assert result.values["author"] == "James Islington"
    assert result.values["publication_year"] == 2025
    assert result.values["book_details"] == "The highly anticipated follow-up to The Will of the Many."


def test_booktopia_nightfall_byline_author_preserves_unavailable_listing_synopsis(monkeypatch):
    provider = BooktopiaProvider()
    _mock_response(monkeypatch, FakeResponse(
        _fixture("nightfall_byline_synthetic.html"), NIGHTFALL_CANONICAL_URL
    ))

    result = MetadataLookupService((provider,)).lookup(NIGHTFALL_ISBN)

    assert result.status == "Retrieved"
    assert result.values["title"] == "Nightfall"
    assert result.values["author"] == "Isaac Asimov"
    assert result.values["publication_year"] == 1991
    assert result.values["book_details"] == "A synthetic unavailable-listing synopsis."
    assert result.provider_statuses["Booktopia"] == "Product unavailable"


def test_booktopia_jsonld_author_takes_precedence_over_visible_byline():
    provider = BooktopiaProvider()
    html = """
      <meta itemprop="isbn" content="9781923058507">
      <script type="application/ld+json">
        {"@type":"Book","isbn":"9781923058507","name":"The Strength of the Few",
         "author":{"@type":"Person","name":"Structured Author"}}
      </script>
      <h1>The Strength of the Few</h1>
      <div>By: Visible Author <button>Write A Review</button></div>
    """

    result = provider._product_result(STRENGTH_URL, html, STRENGTH_ISBN)

    assert result.values["author"] == "Structured Author"


def test_booktopia_direct_isbn_fallback_requires_canonical_redirect(monkeypatch):
    provider = BooktopiaProvider()
    _mock_responses(
        monkeypatch,
        _http_error(NIGHTFALL_SEARCH_URL),
        FakeResponse(_fixture("nightfall_unavailable_synthetic.html"), NIGHTFALL_DIRECT_URL),
    )

    result = provider.lookup(NIGHTFALL_ISBN)

    assert result.status == "Lookup failed"
    assert result.failure_kind == "provider"
    assert result.record_found is None


def test_booktopia_rejects_isbn_mismatch_even_when_redirected_url_matches(monkeypatch):
    provider = BooktopiaProvider()
    _mock_response(monkeypatch, FakeResponse(_fixture("mismatched_product.html")))

    result = provider.lookup(ISBN)

    assert result.status == "No data"
    assert result.record_found is False
    assert result.values == {}


def test_booktopia_rejects_direct_isbn_route_without_canonical_redirect():
    provider = BooktopiaProvider()

    result = provider._product_result(
        f"https://booktopia.com.au/book/{ISBN}.html/",
        _fixture("matching_product.html").decode("utf-8"),
        ISBN,
    )

    assert result.status == "No data"
    assert result.failure_kind == "unverified"
    assert result.record_found is False
    assert result.values == {}


def test_booktopia_reports_matching_product_without_description(monkeypatch):
    provider = BooktopiaProvider()
    _mock_response(monkeypatch, FakeResponse(_fixture("matching_without_description.html")))

    result = provider.lookup(ISBN)

    assert result.status == "Retrieved"
    assert result.record_found is True
    assert result.values == {"title": "Sample Novel"}


def test_booktopia_treats_page_without_isbn_evidence_as_unexpected(monkeypatch):
    provider = BooktopiaProvider()
    _mock_response(monkeypatch, FakeResponse(_fixture("unexpected_page.html"), "https://www.booktopia.com.au/"))

    result = provider.lookup(ISBN)

    assert result.status == "No data"
    assert result.failure_kind == "unverified"


def test_booktopia_does_not_use_generic_meta_description_when_jsonld_is_malformed(monkeypatch):
    provider = BooktopiaProvider()
    _mock_response(monkeypatch, FakeResponse(_fixture("malformed_jsonld.html")))

    result = provider.lookup(ISBN)

    assert result.record_found is True
    assert "book_details" not in result.values


def test_booktopia_follows_only_the_isbn_matching_result_not_the_first_result(monkeypatch):
    provider = BooktopiaProvider()
    called = _mock_responses(
        monkeypatch,
        FakeResponse(_fixture("search_results_multiple.html"), SEARCH_URL),
        FakeResponse(_fixture("matching_product_metadata.html"), PRODUCT_URL),
    )

    result = provider.lookup(ISBN)

    assert [url for url, _timeout in called] == [SEARCH_URL, PRODUCT_URL]
    assert all(0 < timeout <= 5 for _url, timeout in called)
    assert result.record_found is True
    assert result.values["title"] == "Crime and Punishment"
    assert result.values["book_details"] == "A sample verified synopsis."


def test_booktopia_extracts_supported_fields_from_matching_book_jsonld(monkeypatch):
    provider = BooktopiaProvider()
    _mock_response(monkeypatch, FakeResponse(_fixture("matching_product_metadata.html")))

    result = provider.lookup(ISBN)

    assert result.status == "Retrieved"
    assert result.values == {
        "title": "Crime and Punishment",
        "author": "Fyodor Dostoevsky",
        "publisher": "Penguin UK",
        "publication_year": 2003,
        "edition": "1",
        "page_count": 720,
        "format": "Paperback",
        "book_details": "A sample verified synopsis.",
    }


def test_booktopia_prefers_semantic_product_description_to_bibliographic_jsonld_note(monkeypatch):
    provider = BooktopiaProvider()
    _mock_response(monkeypatch, FakeResponse(_fixture("matching_product_bibliographic_note.html")))

    result = provider.lookup(ISBN)

    assert result.record_found is True
    assert result.values["book_details"] == (
        "A desperate student commits a terrible crime in St Petersburg and struggles with its consequences."
    )
    assert "bibliographical references" not in result.values["book_details"]


def test_booktopia_ignores_bibliographic_note_when_description_panel_is_absent():
    provider = BooktopiaProvider()

    result = provider._product_result(
        PRODUCT_URL,
        _fixture("matching_product_bibliographic_note_only.html").decode("utf-8"),
        ISBN,
    )

    assert result.record_found is True
    assert result.values["title"] == "Crime and Punishment"
    assert "book_details" not in result.values


def test_booktopia_does_not_guess_panel_from_description_tab_id_alone():
    provider = BooktopiaProvider()

    result = provider._product_result(
        PRODUCT_URL,
        _fixture("description_tab_without_panel_relation.html").decode("utf-8"),
        ISBN,
    )

    assert result.record_found is True
    assert result.values["title"] == "Crime and Punishment"
    assert "book_details" not in result.values


def test_booktopia_rejects_retail_copy_but_uses_related_description_panel():
    provider = BooktopiaProvider()

    result = provider._product_result(
        STRENGTH_URL,
        _fixture("strength_of_the_few_synthetic.html").decode("utf-8"),
        STRENGTH_ISBN,
    )

    assert result.record_found is True
    assert result.values["title"] == "The Strength of the Few"
    assert result.values["author"] == "James Islington"
    assert result.values["book_details"] == (
        "On three worlds, one young man must hide, fight, and discover what threatens them all."
    )
    assert "Booktopia" not in result.values["book_details"]


def test_strength_of_the_few_synopsis_merges_after_core_metadata_is_complete(monkeypatch):
    class StubProvider:
        def __init__(self, name, result):
            self.name = name
            self.result = result
            self.calls = 0

        def lookup(self, _isbn):
            self.calls += 1
            return self.result

    open_library = StubProvider("Open Library", MetadataResult("Retrieved", {
        "title": "The Strength of the Few", "author": "James Islington", "genre": "Fantasy",
        "publisher": "Text Publishing", "publication_year": 2025,
    }, "Open Library"))
    google_books = StubProvider("Google Books", MetadataResult("No data", {}, "Google Books"))
    booktopia = BooktopiaProvider()
    monkeypatch.setattr(booktopia, "lookup", lambda isbn: booktopia._product_result(
        STRENGTH_URL, _fixture("strength_of_the_few_synthetic.html").decode("utf-8"), isbn
    ))

    result = MetadataLookupService((open_library, google_books, booktopia)).lookup(STRENGTH_ISBN)

    assert [open_library.calls, google_books.calls] == [1, 1]
    assert result.values["title"] == "The Strength of the Few"
    assert result.values["author"] == "James Islington"
    assert result.values["book_details"] == (
        "On three worlds, one young man must hide, fight, and discover what threatens them all."
    )


def test_booktopia_rejects_retail_copy_from_meta_and_book_jsonld():
    provider = BooktopiaProvider()

    result = provider._product_result(
        STRENGTH_URL,
        _fixture("matching_product_retail_copy_only.html").decode("utf-8"),
        STRENGTH_ISBN,
    )

    assert result.record_found is True
    assert result.values["title"] == "The Strength of the Few"
    assert "book_details" not in result.values


def test_booktopia_matching_unavailable_page_can_supply_a_verified_synopsis():
    provider = BooktopiaProvider()
    product_result = provider._product_result(
        UNAVAILABLE_URL,
        _fixture("unavailable_matching_product_synthetic.html").decode("utf-8"),
        UNAVAILABLE_ISBN,
    )
    assert product_result.record_found is True
    assert product_result.failure_kind == "unavailable"
    assert product_result.values["book_details"] == "A synthetic narrative description for regression testing."

    class ResultProvider:
        name = "Booktopia"

        def lookup(self, _isbn):
            return product_result

    result = MetadataLookupService((ResultProvider(),)).lookup(UNAVAILABLE_ISBN)

    assert result.status == "Retrieved"
    assert result.values["title"] == "Synthetic Unavailable Book"
    assert result.values["book_details"] == "A synthetic narrative description for regression testing."
    assert result.provider_statuses["Booktopia"] == "Product unavailable"


def test_booktopia_matching_structured_out_of_stock_offer_is_unavailable():
    provider = BooktopiaProvider()
    html = """
      <script type="application/ld+json">
        {"@type":"Book","isbn":"9780306406157","name":"Synthetic Unavailable Book",
         "offers":{"@type":"Offer","availability":"https://schema.org/OutOfStock"}}
      </script>
    """

    result = provider._product_result(UNAVAILABLE_URL, html, UNAVAILABLE_ISBN)

    assert result.record_found is True
    assert result.failure_kind == "unavailable"


def test_booktopia_does_not_accept_matching_url_without_page_isbn_evidence(monkeypatch):
    provider = BooktopiaProvider()
    _mock_response(monkeypatch, FakeResponse(_fixture("unexpected_page.html"), PRODUCT_URL))

    result = provider.lookup(ISBN)

    assert result.status == "No data"
    assert result.failure_kind == "unverified"
    assert result.values == {}


def test_booktopia_does_not_request_invalid_isbn(monkeypatch):
    provider = BooktopiaProvider()
    called = _mock_response(monkeypatch, FakeResponse(_fixture("matching_product.html")))

    result = provider.lookup("9780140449137")

    assert called == []
    assert result.status == "No data"
    assert result.failure_kind == "unverified"


def test_booktopia_accepts_isbn10_alias_of_product_isbn13(monkeypatch):
    provider = BooktopiaProvider()
    _mock_response(monkeypatch, FakeResponse(_fixture("matching_product.html")))

    result = provider.lookup("0140449132")

    assert result.status == "Retrieved"
    assert "book_details" in result.values


def test_booktopia_rejects_redirects_outside_booktopia(monkeypatch):
    provider = BooktopiaProvider()
    _mock_response(monkeypatch, FakeResponse(_fixture("matching_product.html"), "https://example.com/book.html"))

    result = provider.lookup(ISBN)

    assert result.status == "Lookup failed"
    assert result.failure_kind == "unexpected"


def test_booktopia_rejects_oversized_response(monkeypatch):
    provider = BooktopiaProvider()
    _mock_response(monkeypatch, FakeResponse(b"x" * (2 * 1024 * 1024 + 1)))

    result = provider.lookup(ISBN)

    assert result.status == "Lookup failed"
    assert result.failure_kind == "unexpected"


def test_redirect_handler_allows_canonical_booktopia_page_but_rejects_other_hosts():
    handler = _BooktopiaRedirectHandler()
    request = Request(f"https://www.booktopia.com.au/book/{ISBN}.html/")

    redirected = handler.redirect_request(
        request, None, 301, "Moved", {}, PRODUCT_URL
    )

    assert redirected.full_url == PRODUCT_URL
    with pytest.raises(ValueError):
        handler.redirect_request(request, None, 302, "Found", {}, "http://127.0.0.1/internal")


def test_booktopia_search_404_is_reported_as_a_provider_error(monkeypatch):
    provider = BooktopiaProvider()
    called = _mock_responses(
        monkeypatch,
        _http_error(SEARCH_URL),
        _http_error(f"https://booktopia.com.au/book/{ISBN}.html/"),
    )
    result = provider.lookup(ISBN)

    assert [url for url, _timeout in called] == [SEARCH_URL, f"https://booktopia.com.au/book/{ISBN}.html/"]
    assert all(0 < timeout <= 5 for _url, timeout in called)
    assert result.status == "Lookup failed"
    assert result.failure_kind == "provider"
    assert result.record_found is None


def test_booktopia_candidate_404_is_not_treated_as_an_isbn_miss(monkeypatch):
    provider = BooktopiaProvider()
    candidate_missing = _http_error(PRODUCT_URL)
    _mock_responses(
        monkeypatch,
        FakeResponse(_fixture("search_results_multiple.html"), SEARCH_URL),
        candidate_missing,
    )

    result = provider.lookup(ISBN)

    assert result.status == "Lookup failed"
    assert result.failure_kind == "provider"
    assert result.record_found is None


def test_booktopia_candidate_http_error_body_is_used_only_when_isbn_verifies(monkeypatch):
    provider = BooktopiaProvider()
    wrong_isbn_page = _http_error(PRODUCT_URL, _fixture("mismatched_product.html"))
    _mock_responses(
        monkeypatch,
        FakeResponse(_fixture("search_results_multiple.html"), SEARCH_URL),
        wrong_isbn_page,
    )

    result = provider.lookup(ISBN)

    assert result.status == "Lookup failed"
    assert result.failure_kind == "provider"
    assert result.record_found is None


def test_booktopia_candidate_http_error_body_can_supply_unavailable_product_data(monkeypatch):
    provider = BooktopiaProvider()
    product_error = _http_error(
        UNAVAILABLE_URL,
        _fixture("unavailable_matching_product_synthetic.html"),
    )
    search_html = f'<a href="{UNAVAILABLE_URL}">matching ISBN product</a>'.encode()
    search_url = "https://www.booktopia.com.au/search.ep?keywords=9780306406157"
    _mock_responses(
        monkeypatch,
        FakeResponse(search_html, search_url),
        product_error,
    )

    result = provider.lookup(UNAVAILABLE_ISBN)

    assert result.status == "Retrieved"
    assert result.record_found is True
    assert result.failure_kind == "unavailable"
    assert result.values["book_details"] == "A synthetic narrative description for regression testing."


def test_booktopia_reports_provider_http_errors_without_calling_them_a_miss(monkeypatch):
    provider = BooktopiaProvider()

    def unavailable(*_args, **_kwargs):
        raise urllib.error.HTTPError("https://www.booktopia.com.au/search.ep", 503, "Unavailable", {}, None)

    monkeypatch.setattr("bookledger.services.booktopia.BooktopiaProvider._open", unavailable)
    result = provider.lookup(ISBN)

    assert result.status == "Lookup failed"
    assert result.failure_kind == "provider"
    assert result.record_found is None


def test_booktopia_reports_search_timeout(monkeypatch):
    provider = BooktopiaProvider()

    def timed_out(*_args, **_kwargs):
        raise TimeoutError("internal timeout detail")

    monkeypatch.setattr("bookledger.services.booktopia.BooktopiaProvider._open", timed_out)
    result = provider.lookup(ISBN)

    assert result.status == "Lookup failed"
    assert result.failure_kind == "timeout"
    assert result.values == {}


def test_booktopia_failure_does_not_discard_existing_provider_metadata():
    class StubProvider:
        def __init__(self, name, result):
            self.name = name
            self.result = result

        def lookup(self, _isbn):
            return self.result

    open_library = StubProvider("Open Library", MetadataResult("Retrieved", {"title": "Novel"}, "Open Library"))
    google_books = StubProvider("Google Books", MetadataResult("Retrieved", {"author": "Author"}, "Google Books"))
    booktopia = StubProvider("Booktopia", MetadataResult("Lookup failed", {}, "Booktopia", "timeout", "timeout"))

    result = MetadataLookupService((open_library, google_books, booktopia)).lookup(ISBN)

    assert result.status == "Retrieved"
    assert result.partial is True
    assert result.values == {"title": "Novel", "author": "Author"}
    assert result.provider_statuses["Booktopia"] == "Timed out"


def test_booktopia_runs_last_to_fill_only_a_missing_description():
    class StubProvider:
        def __init__(self, name, values):
            self.name = name
            self.values = values
            self.calls = 0

        def lookup(self, _isbn):
            self.calls += 1
            if not self.values:
                return MetadataResult("No data", {}, self.name, record_found=False)
            return MetadataResult("Retrieved", self.values, self.name)

    open_library = StubProvider("Open Library", {"title": "Primary title", "author": "Author"})
    google_books = StubProvider("Google Books", {"publisher": "Press", "genre": "Fiction"})
    booktopia = StubProvider("Booktopia", {"book_details": "Description"})
    statuses = []

    result = MetadataLookupService((open_library, google_books, booktopia)).lookup(
        ISBN, on_provider_status=lambda provider, status: statuses.append((provider, status))
    )

    assert result.values == {
        "title": "Primary Title", "author": "Author", "publisher": "Press",
        "genre": "Fiction", "book_details": "Description",
    }
    assert booktopia.calls == 1
    assert not any(status.startswith("Waiting") for _name, status in statuses)
    assert ("Booktopia", "Retrieving from Booktopia…") in statuses
    assert result.provider_statuses["Booktopia"] == "Metadata retrieved · some fields missing"


def test_google_books_is_queried_for_supported_metadata_still_missing():
    class StubProvider:
        def __init__(self, name, values):
            self.name = name
            self.values = values
            self.calls = 0

        def lookup(self, _isbn):
            self.calls += 1
            return MetadataResult("Retrieved", self.values, self.name)

    open_library = StubProvider("Open Library", {
        "title": "Novel", "author": "Author", "genre": "Fiction", "publisher": "Press",
        "publication_year": 2020, "page_count": 200, "edition": "First",
    })
    google_books = StubProvider("Google Books", {"book_details": "A full synopsis."})

    result = MetadataLookupService((open_library, google_books)).lookup(ISBN)

    assert google_books.calls == 1
    assert result.values["book_details"] == "A full synopsis."
    assert result.partial is False


def test_booktopia_runs_when_its_unique_format_field_is_missing():
    class StubProvider:
        def __init__(self, name, values):
            self.name = name
            self.values = values
            self.calls = 0

        def lookup(self, _isbn):
            self.calls += 1
            if not self.values:
                return MetadataResult("No data", {}, self.name, record_found=False)
            return MetadataResult("Retrieved", self.values, self.name)

    open_library = StubProvider("Open Library", {
        "title": "Novel", "author": "Author", "genre": "Fiction",
        "publisher": "Press", "publication_year": 2020,
    })
    google_books = StubProvider("Google Books", {})
    booktopia = StubProvider("Booktopia", {"book_details": "Booktopia description"})

    result = MetadataLookupService((open_library, google_books, booktopia)).lookup(ISBN)

    assert booktopia.calls == 1
    assert result.values["book_details"] == "Booktopia description"
    assert result.provider_statuses["Booktopia"] == "Metadata retrieved · some fields missing"


def test_booktopia_enriches_missing_metadata_without_replacing_prior_provider_values():
    class StubProvider:
        def __init__(self, name, values):
            self.name = name
            self.values = values
            self.calls = 0

        def lookup(self, _isbn):
            self.calls += 1
            return MetadataResult("Retrieved", self.values, self.name, record_found=True)

    open_library = StubProvider("Open Library", {
        "title": "Crime and Punishment", "author": "Fyodor Dostoevsky", "page_count": 671,
    })
    google_books = StubProvider("Google Books", {"publisher": "Google Books Press"})
    booktopia = StubProvider("Booktopia", {
        "title": "Different title", "author": "Different author", "publisher": "Penguin UK",
        "publication_year": 2003, "edition": "1", "page_count": 720, "format": "Paperback",
        "book_details": "A sample verified synopsis.",
    })

    result = MetadataLookupService((open_library, google_books, booktopia)).lookup(ISBN)

    assert booktopia.calls == 1
    assert result.values == {
        "title": "Crime and Punishment", "author": "Fyodor Dostoevsky", "page_count": 671,
        "publisher": "Google Books Press", "publication_year": 2003, "edition": "1",
        "format": "Paperback", "book_details": "A sample verified synopsis.",
    }


def test_default_metadata_lookup_keeps_booktopia_after_primary_and_fallback():
    service = MetadataLookupService()

    assert [provider.name for provider in service.providers] == [
        "Open Library", "Google Books", "Booktopia",
    ]
