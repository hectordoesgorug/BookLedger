from unittest.mock import MagicMock, patch
import urllib.error
import urllib.parse

from bookledger.services.metadata import (
    GoogleBooksProvider,
    MetadataLookupService,
    normalize_provider_title,
    MetadataProvider,
    MetadataResult,
    OpenLibraryProvider,
)


class StubProvider(MetadataProvider):
    def __init__(self, name, result):
        self.name = name
        self.result = result
        self.calls = 0

    def lookup(self, isbn):
        self.calls += 1
        return self.result


def test_open_library_normalizes_book_fields_and_uses_isbn_key():
    provider = OpenLibraryProvider()
    provider._request_json = lambda _url: {
        "ISBN:9780306406157": {
            "title": "Example Book",
            "authors": [{"name": "A. Author"}],
            "publishers": [{"name": "Example Press"}],
            "publish_date": "2020",
            "number_of_pages": 123,
            "subjects": [{"name": "Science"}],
        }
    }

    result = provider.lookup("978-0-306-40615-7")

    assert result.status == "Retrieved"
    assert result.source == "Open Library"
    assert result.values["title"] == "Example Book"
    assert result.values["author"] == "A. Author"
    assert result.values["genre"] == "Science"


def test_google_books_requires_a_matching_isbn_identifier():
    provider = GoogleBooksProvider()
    provider._request_json = lambda _url: {
        "items": [{"volumeInfo": {"title": "Wrong Book", "industryIdentifiers": [{"identifier": "9780000000002"}]}}]
    }

    result = provider.lookup("9780306406157")

    assert result.status == "No data"
    assert result.values == {}


def test_google_books_api_key_is_optional_and_only_added_when_configured():
    provider = GoogleBooksProvider("private-test-key")
    requested = []
    provider._request_json = lambda url: (requested.append(url) or {"items": []})
    assert provider.lookup("9780306406157").status == "No data"
    assert urllib.parse.parse_qs(urllib.parse.urlparse(requested[0]).query)["key"] == ["private-test-key"]
    no_key = GoogleBooksProvider()
    no_key._request_json = lambda url: (requested.append(url) or {"items": []})
    no_key.lookup("9780306406157")
    assert "key" not in urllib.parse.parse_qs(urllib.parse.urlparse(requested[1]).query)


def test_matching_record_without_usable_metadata_is_a_miss():
    provider = OpenLibraryProvider()
    provider._request_json = lambda _url: {"ISBN:9780306406157": {"identifiers": {"isbn_13": ["9780306406157"]}}}

    result = provider.lookup("9780306406157")

    assert result.status == "No data"
    assert result.values == {}


def test_each_metadata_provider_uses_its_own_ten_second_request_timeout():
    response = MagicMock()
    response.__enter__.return_value.read.return_value = b"{}"
    for provider in (OpenLibraryProvider(), GoogleBooksProvider()):
        with patch("bookledger.services.metadata.urllib.request.urlopen", return_value=response) as urlopen:
            provider._request_json("https://example.test/lookup")
        assert urlopen.call_args.kwargs["timeout"] == 10


def test_lookup_service_falls_back_and_reports_provider_progress():
    first = StubProvider("Open Library", MetadataResult("No data", {}, "Open Library"))
    fallback = StubProvider("Google Books", MetadataResult("Retrieved", {"title": "Book"}, "Google Books"))
    progress = []

    result = MetadataLookupService((first, fallback)).lookup("9780306406157", on_status=progress.append)

    assert result.source == "Google Books"
    assert first.calls == fallback.calls == 1
    assert progress == [
        "Searching ISBN: Open Library",
        "Fetching Data…",
        "Searching ISBN: Google Books",
        "Fetching Data…",
    ]


def test_provider_statuses_keep_primary_success_and_skip_google_books():
    primary = StubProvider("Open Library", MetadataResult("Retrieved", {
        "title": "Book", "author": "Author", "genre": "Science", "book_details": "Details",
        "publisher": "Press", "publication_year": 2020, "edition": "First", "page_count": 100,
    }, "Open Library"))
    fallback = StubProvider("Google Books", MetadataResult("Retrieved", {"title": "Google title"}, "Google Books"))
    statuses = []

    result = MetadataLookupService((primary, fallback)).lookup(
        "9780306406157", on_provider_status=lambda name, status: statuses.append((name, status))
    )

    assert result.values["title"] == "Book"
    assert primary.calls == 1
    assert fallback.calls == 0
    assert result.provider_statuses == {
        "Open Library": "Metadata retrieved",
        "Google Books": "Not needed (skipped)",
    }
    assert ("Open Library", "Retrieving from Open Library…") in statuses
    assert ("Google Books", "Waiting for Open Library…") in statuses


def test_provider_statuses_report_no_match_then_google_books_success():
    primary = StubProvider("Open Library", MetadataResult("No data", {}, "Open Library", record_found=False))
    fallback = StubProvider("Google Books", MetadataResult("Retrieved", {"title": "Fallback"}, "Google Books", record_found=True))

    result = MetadataLookupService((primary, fallback)).lookup("9780306406157")

    assert result.status == "Retrieved"
    assert result.provider_statuses["Open Library"] == "No matching record"
    assert result.provider_statuses["Google Books"] == "Metadata retrieved · some fields missing"


def test_provider_statuses_report_timeout_and_still_attempt_google_books():
    primary = StubProvider("Open Library", MetadataResult("Lookup failed", {}, "Open Library", "secret diagnostic", "timeout"))
    fallback = StubProvider("Google Books", MetadataResult("Retrieved", {"title": "Fallback"}, "Google Books"))

    result = MetadataLookupService((primary, fallback)).lookup("9780306406157")

    assert primary.calls == fallback.calls == 1
    assert result.provider_statuses == {
        "Open Library": "Timed out",
        "Google Books": "Metadata retrieved · some fields missing",
    }
    assert result.partial is True


def test_both_provider_misses_are_reported_without_calling_them_failures():
    primary = StubProvider("Open Library", MetadataResult("No data", {}, "Open Library", record_found=False))
    fallback = StubProvider("Google Books", MetadataResult("No data", {}, "Google Books", record_found=False))

    result = MetadataLookupService((primary, fallback)).lookup("9780306406157")

    assert result.status == "No data"
    assert result.record_found is False
    assert result.provider_statuses == {"Open Library": "No matching record", "Google Books": "No matching record"}


def test_different_provider_errors_have_independent_safe_statuses():
    primary = StubProvider("Open Library", MetadataResult("Lookup failed", {}, "Open Library", "timeout detail", "timeout"))
    fallback = StubProvider("Google Books", MetadataResult("Lookup failed", {}, "Google Books", "HTTP 503 detail", "provider"))

    result = MetadataLookupService((primary, fallback)).lookup("9780306406157")

    assert result.status == "Lookup failed"
    assert result.provider_statuses == {"Open Library": "Timed out", "Google Books": "HTTP/provider error"}
    assert "detail" not in " ".join(result.provider_statuses.values())


def test_matching_record_with_no_usable_fields_is_not_reported_as_isbn_miss():
    provider = OpenLibraryProvider()
    provider._request_json = lambda _url: {
        "ISBN:9780306406157": {"identifiers": {"isbn_13": ["9780306406157"]}}
    }
    statuses = []
    service = MetadataLookupService((provider,))

    result = service.lookup("9780306406157", on_provider_status=lambda name, status: statuses.append((name, status)))

    assert result.status == "No data"
    assert result.record_found is True
    assert result.provider_statuses["Open Library"] == "Record found · supported metadata unavailable"


def test_unexpected_provider_response_is_not_reported_as_a_miss():
    provider = OpenLibraryProvider()
    provider._request_json = lambda _url: (_ for _ in ()).throw(ValueError("malformed provider payload"))

    result = MetadataLookupService((provider,)).lookup("9780306406157")

    assert result.status == "Lookup failed"
    assert result.failure_kind == "unexpected"
    assert result.provider_statuses["Open Library"] == "Unexpected response error"


def test_successful_google_fallback_after_open_library_failure_keeps_failure_diagnostic():
    primary = StubProvider(
        "Open Library",
        MetadataResult("Lookup failed", {}, "Open Library", "connection timed out", "timeout"),
    )
    fallback = StubProvider(
        "Google Books",
        MetadataResult("Retrieved", {"title": "Fallback Book", "publisher": "Fallback Press"}, "Google Books"),
    )

    result = MetadataLookupService((primary, fallback)).lookup("9780306406157")

    assert primary.calls == fallback.calls == 1
    assert result.status == "Retrieved"
    assert result.values["title"] == "Fallback Book"
    assert result.source == "Google Books"
    assert result.error == "connection timed out"
    assert result.failure_kind == "timeout"


def test_lookup_service_fills_partial_metadata_without_replacing_primary_values():
    first = StubProvider("Open Library", MetadataResult("Retrieved", {"title": "Primary title", "author": "Primary author"}, "Open Library"))
    fallback = StubProvider("Google Books", MetadataResult("Retrieved", {"title": "Fallback title", "publisher": "Fallback press", "page_count": 140}, "Google Books"))
    result = MetadataLookupService((first, fallback)).lookup("9780306406157")
    assert result.status == "Retrieved"
    assert result.values["title"] == "Primary Title"
    assert result.values["author"] == "Primary author"
    assert result.values["publisher"] == "Fallback press"
    assert result.values["page_count"] == 140
    assert result.source == "Open Library + Google Books"


def test_provider_title_normalization_handles_small_words_punctuation_and_acronyms():
    assert normalize_provider_title("THE ART OF WAR") == "The Art of War"
    assert normalize_provider_title("the great gatsby") == "The Great Gatsby"
    assert normalize_provider_title("INTRODUCTION TO SOCIAL SCIENCE") == "Introduction to Social Science"
    assert normalize_provider_title("NASA: an API guide to ISBN-13") == "NASA: An API Guide to ISBN-13"


def test_lookup_service_distinguishes_miss_from_technical_failure():
    miss = MetadataLookupService((StubProvider("Open Library", MetadataResult("No data", {}, "Open Library")),))
    timeout = MetadataLookupService((StubProvider("Open Library", MetadataResult("Lookup failed", {}, "Open Library", "timed out", "timeout")),))

    assert miss.lookup("9780306406157").status == "No data"
    result = timeout.lookup("9780306406157")
    assert result.status == "Lookup failed"
    assert result.failure_kind == "timeout"


def test_provider_classifies_network_unavailable_error():
    provider = OpenLibraryProvider()
    provider._request_json = lambda _url: (_ for _ in ()).throw(urllib.error.URLError(ConnectionError("offline")))

    result = provider.lookup("9780306406157")

    assert result.status == "Lookup failed"
    assert result.failure_kind == "network"
