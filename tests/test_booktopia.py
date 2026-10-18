from email.message import Message
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

    assert called == [(SEARCH_URL, 10)]
    assert result.status == "Retrieved"
    assert result.record_found is True
    assert result.values == {
        "title": "Sample Novel",
        "book_details": "Product description with nested markup.",
    }


def test_booktopia_rejects_isbn_mismatch_even_when_redirected_url_matches(monkeypatch):
    provider = BooktopiaProvider()
    _mock_response(monkeypatch, FakeResponse(_fixture("mismatched_product.html")))

    result = provider.lookup(ISBN)

    assert result.status == "No data"
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


def test_booktopia_uses_standard_description_when_jsonld_is_malformed(monkeypatch):
    provider = BooktopiaProvider()
    _mock_response(monkeypatch, FakeResponse(_fixture("malformed_jsonld.html")))

    result = provider.lookup(ISBN)

    assert result.status == "Retrieved"
    assert result.values == {"book_details": "Readable description metadata."}


def test_booktopia_follows_only_the_isbn_matching_result_not_the_first_result(monkeypatch):
    provider = BooktopiaProvider()
    called = _mock_responses(
        monkeypatch,
        FakeResponse(_fixture("search_results_multiple.html"), SEARCH_URL),
        FakeResponse(_fixture("matching_product_metadata.html"), PRODUCT_URL),
    )

    result = provider.lookup(ISBN)

    assert called == [(SEARCH_URL, 10), (PRODUCT_URL, 10)]
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

    def missing(*_args, **_kwargs):
        raise urllib.error.HTTPError("https://www.booktopia.com.au/", 404, "Not Found", {}, None)

    monkeypatch.setattr("bookledger.services.booktopia.BooktopiaProvider._open", lambda *_args: missing())
    result = provider.lookup(ISBN)

    assert result.status == "Lookup failed"
    assert result.failure_kind == "provider"
    assert result.record_found is None


def test_booktopia_candidate_404_is_not_treated_as_an_isbn_miss(monkeypatch):
    provider = BooktopiaProvider()
    candidate_missing = urllib.error.HTTPError(
        PRODUCT_URL, 404, "Not Found", {}, None
    )
    _mock_responses(
        monkeypatch,
        FakeResponse(_fixture("search_results_multiple.html"), SEARCH_URL),
        candidate_missing,
    )

    result = provider.lookup(ISBN)

    assert result.status == "Lookup failed"
    assert result.failure_kind == "provider"
    assert result.record_found is None


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
    assert ("Booktopia", "Waiting for Google Books…") in statuses
    assert ("Booktopia", "Retrieving from Booktopia…") in statuses
    assert result.provider_statuses["Booktopia"] == "Metadata retrieved · some fields missing"


def test_google_books_is_not_skipped_when_book_details_is_the_only_missing_supported_field():
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
        "publication_year": 2020, "page_count": 200,
    })
    google_books = StubProvider("Google Books", {"book_details": "A full synopsis."})

    result = MetadataLookupService((open_library, google_books)).lookup(ISBN)

    assert google_books.calls == 1
    assert result.provider_statuses["Google Books"] != "Not needed (skipped)"
    assert result.values["book_details"] == "A full synopsis."


def test_booktopia_is_skipped_when_earlier_providers_supply_all_supported_fields():
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
        "title": "Novel", "author": "Author", "genre": "Fiction", "book_details": "Existing description",
        "publisher": "Press", "publication_year": 2020, "edition": "First", "page_count": 100,
        "format": "Paperback",
    })
    google_books = StubProvider("Google Books", {})
    booktopia = StubProvider("Booktopia", {"book_details": "Booktopia description"})

    result = MetadataLookupService((open_library, google_books, booktopia)).lookup(ISBN)

    assert booktopia.calls == 0
    assert result.values["book_details"] == "Existing description"
    assert result.provider_statuses["Booktopia"] == "Not needed (skipped)"


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
