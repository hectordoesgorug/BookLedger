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
from bookledger.services.isbn import equivalent_isbn, isbn_check


INVESTIGATION_ISBNS = (
    ("9780385504201", "0385504209"),
    ("9780387001678", "0387001670"),
    ("9780345387738", "0345387732"),
    ("9780552997041", "0552997048"),
    ("9780140449136", "0140449132"),
)

REFERENCE_ISBNS = (
    "9780060515195",  # Anansi Boys
    "9780345351739",  # 2061
    "9780330352888",  # Invasion
    "9780060846268",  # The Magdalene Cipher
    "9780387004365",  # Centauri Dreams
    "9780802713513",  # Measuring the Universe
    "9780688123307",  # Wrinkles in Time
    "9780553070842",  # The Ascent of Mind
    "9780805056693",  # Wild Minds
    "9780133266795",  # Foundations of Analysis
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


def test_investigation_isbns_are_valid_and_have_expected_isbn10_aliases():
    for isbn13, isbn10 in INVESTIGATION_ISBNS:
        assert isbn_check(isbn13)[0]
        assert isbn_check(isbn10)[0]
        assert equivalent_isbn(isbn13) == isbn10
        assert equivalent_isbn(isbn10) == isbn13


def test_both_providers_query_exact_input_then_try_valid_isbn_aliases():
    for isbn13, isbn10 in INVESTIGATION_ISBNS:
        open_library_queries = []
        open_library = OpenLibraryProvider()
        open_library._request_json = lambda url: (
            open_library_queries.append(urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["bibkeys"][0])
            or {}
        )
        assert open_library.lookup(isbn13).status == "No data"
        assert open_library_queries == [f"ISBN:{isbn13},ISBN:{isbn10}"]

        google_queries = []
        google_books = GoogleBooksProvider()
        google_books._request_json = lambda url: (
            google_queries.append(urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["q"][0])
            or {"items": []}
        )
        assert google_books.lookup(isbn13).status == "No data"
        assert google_queries == [isbn13, f"isbn:{isbn13}", f"isbn:{isbn10}"]


def test_ten_legacy_reference_isbns_use_valid_alias_query_paths():
    for isbn13 in REFERENCE_ISBNS:
        isbn10 = equivalent_isbn(isbn13)
        assert isbn_check(isbn13)[0]
        assert isbn10 and isbn_check(isbn10)[0]

        open_library_queries = []
        open_library = OpenLibraryProvider()
        open_library._request_json = lambda url: (
            open_library_queries.append(urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["bibkeys"][0])
            or {}
        )
        assert open_library.lookup(isbn13).record_found is False
        assert open_library_queries == [f"ISBN:{isbn13},ISBN:{isbn10}"]

        google_queries = []
        google_books = GoogleBooksProvider()
        google_books._request_json = lambda url: (
            google_queries.append(urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["q"][0])
            or {"items": []}
        )
        assert google_books.lookup(isbn13).record_found is False
        assert google_queries == [isbn13, f"isbn:{isbn13}", f"isbn:{isbn10}"]


def test_open_library_queries_both_isbn_forms_and_accepts_equivalent_identifier():
    requested = []
    provider = OpenLibraryProvider()

    def response(url):
        requested.append(urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["bibkeys"][0])
        return {
            "ISBN:0385504209": {
                "identifiers": {"isbn_10": ["0-385-50420-9"]},
                "title": "The Da Vinci Code",
            }
        }

    provider._request_json = response
    result = provider.lookup("9780385504201")

    assert requested == ["ISBN:9780385504201,ISBN:0385504209"]
    assert result.record_found is True
    assert result.values["title"] == "The Da Vinci Code"


def test_open_library_mismatched_returned_identifiers_are_not_classified_as_a_miss():
    provider = OpenLibraryProvider()
    provider._request_json = lambda _url: {
        "ISBN:9780385504201": {
            "identifiers": {"isbn_13": ["9780000000002"]},
            "title": "Different book",
        },
        "ISBN:0385504209": {
            "identifiers": {"isbn_10": ["0000000000"]},
            "title": "Different book",
        },
    }

    result = provider.lookup("9780385504201")

    assert result.status == "No data"
    assert result.failure_kind == "unverified"
    assert result.record_found is False


def test_open_library_extracts_dictionary_notes_excerpts_and_work_descriptions():
    provider = OpenLibraryProvider()
    calls = []

    def response(url):
        calls.append(url)
        if url.endswith(".json"):
            return {"description": {"value": "Work-level complete description."}}
        return {
            "ISBN:9780306406157": {
                "identifiers": {"isbn_13": ["9780306406157"]},
                "title": "Example",
                "notes": {"type": "/type/text", "value": "Edition-level note."},
                "works": [{"key": "/works/OL123W"}],
            }
        }

    provider._request_json = response
    result = provider.lookup("9780306406157")
    assert result.values["book_details"] == "Edition-level note."
    assert len(calls) == 1

    def no_edition_description(url):
        if url.endswith(".json"):
            return {"description": "Work-level complete description."}
        return {
            "ISBN:9780306406157": {
                "identifiers": {"isbn_13": ["9780306406157"]},
                "excerpts": [{"excerpt": "Excerpt description."}],
                "works": [{"key": "/works/OL123W"}],
            }
        }

    provider._request_json = no_edition_description
    assert provider.lookup("9780306406157").values["book_details"] == "Excerpt description."

    def work_description(url):
        if url.endswith(".json"):
            return {"description": {"value": "Work-level complete description."}}
        return {
            "ISBN:9780306406157": {
                "identifiers": {"isbn_13": ["9780306406157"]},
                "title": "Example",
                "works": [{"key": "/works/OL123W"}],
            }
        }

    provider._request_json = work_description
    assert provider.lookup("9780306406157").values["book_details"] == "Work-level complete description."


def test_open_library_prefers_edition_description_string_and_object_shapes():
    provider = OpenLibraryProvider()

    for description in ("Edition string description.", {"type": "/type/text", "value": "Edition object description."}):
        provider._request_json = lambda _url, description=description: {
            "ISBN:9780306406157": {
                "identifiers": {"isbn_13": ["9780306406157"]},
                "description": description,
                "notes": {"value": "Weaker notes fallback."},
                "excerpts": [{"excerpt": "Weaker excerpt fallback."}],
            }
        }
        result = provider.lookup("9780306406157")
        expected = description if isinstance(description, str) else description["value"]
        assert result.values["book_details"] == expected


def test_open_library_ignores_malformed_description_and_returns_none_when_unusable():
    provider = OpenLibraryProvider()

    provider._request_json = lambda _url: {
        "ISBN:9780306406157": {
            "identifiers": {"isbn_13": ["9780306406157"]},
            "title": "Example",
            "description": {"value": 42, "unexpected": [None]},
            "notes": {"type": "/type/text", "value": "Usable notes fallback."},
        }
    }
    assert provider.lookup("9780306406157").values["book_details"] == "Usable notes fallback."

    provider._request_json = lambda _url: {
        "ISBN:9780306406157": {
            "identifiers": {"isbn_13": ["9780306406157"]},
            "title": "Example",
            "description": {"value": 42, "unexpected": [None]},
            "notes": {"value": "   "},
            "excerpts": [],
        }
    }
    result = provider.lookup("9780306406157")
    assert result.status == "Retrieved"
    assert result.values["title"] == "Example"
    assert result.values["book_details"] is None


def test_open_library_optional_work_description_failure_keeps_edition_metadata():
    provider = OpenLibraryProvider()

    def response(url):
        if url.endswith(".json"):
            raise TimeoutError("work description timed out")
        return {
            "ISBN:9780306406157": {
                "identifiers": {"isbn_13": ["9780306406157"]},
                "title": "Example",
                "works": [{"key": "/works/OL123W"}],
            }
        }

    provider._request_json = response
    result = provider.lookup("9780306406157")
    assert result.status == "Retrieved"
    assert result.values["title"] == "Example"
    assert result.values["book_details"] is None


def test_google_books_retries_with_equivalent_isbn_and_accepts_alias_identifier():
    provider = GoogleBooksProvider()
    requested = []

    def response(url):
        query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["q"][0]
        requested.append(query)
        if query != "isbn:0385504209":
            return {"items": []}
        return {
            "items": [{"volumeInfo": {
                "title": "The Da Vinci Code",
                "industryIdentifiers": [{"type": "ISBN_10", "identifier": "0-385-50420-9"}],
                "description": "Full provider description.",
            }}]
        }

    provider._request_json = response
    result = provider.lookup("9780385504201")

    assert requested == ["9780385504201", "isbn:9780385504201", "isbn:0385504209"]
    assert result.record_found is True
    assert result.values["book_details"] == "Full provider description."


def test_google_books_scans_matching_volumes_without_accepting_unrelated_description():
    provider = GoogleBooksProvider()
    requested = []

    def response(url):
        query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["q"][0]
        requested.append(query)
        return {"items": [
            {"volumeInfo": {
                "title": "Unrelated volume",
                "industryIdentifiers": [{"identifier": "9780000000002"}],
                "description": "Unrelated description must not be used.",
                "publisher": "Unrelated Press",
            }},
            {"volumeInfo": {
                "title": "First verified title",
                "industryIdentifiers": [{"identifier": "9780385504201"}],
            }},
            {"volumeInfo": {
                "title": "Second verified title",
                "industryIdentifiers": [{"identifier": "0-385-50420-9"}],
                "description": "Useful target description.",
            }},
        ]}

    provider._request_json = response
    result = provider.lookup("9780385504201")

    assert requested == ["9780385504201"]
    assert result.values["title"] == "First verified title"
    assert result.values["book_details"] == "Useful target description."
    assert "publisher" not in result.values


def test_google_books_continues_query_variants_after_sparse_matching_volume():
    provider = GoogleBooksProvider()
    requested = []

    def response(url):
        query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["q"][0]
        requested.append(query)
        if query == "9780385504201":
            return {"items": [{"volumeInfo": {
                "title": "Sparse verified match",
                "industryIdentifiers": [{"identifier": "9780385504201"}],
            }}]}
        if query == "isbn:9780385504201":
            return {"items": [{"volumeInfo": {
                "industryIdentifiers": [{"identifier": "0-385-50420-9"}],
                "description": "Description from a later verified query.",
            }}]}
        return {"items": []}

    provider._request_json = response
    result = provider.lookup("9780385504201")

    assert requested == ["9780385504201", "isbn:9780385504201"]
    assert result.values["title"] == "Sparse verified match"
    assert result.values["book_details"] == "Description from a later verified query."


def test_google_books_does_not_report_a_miss_when_an_isbn_variant_request_fails():
    provider = GoogleBooksProvider()
    calls = []

    def response(_url):
        calls.append(1)
        if len(calls) == 1:
            return {"items": []}
        raise urllib.error.URLError(ConnectionError("offline"))

    provider._request_json = response
    result = provider.lookup("9780385504201")
    assert result.status == "Lookup failed"
    assert result.failure_kind == "network"


def test_google_books_requires_a_matching_isbn_identifier():
    provider = GoogleBooksProvider()
    provider._request_json = lambda _url: {
        "items": [{"volumeInfo": {"title": "Wrong Book", "industryIdentifiers": [{"identifier": "9780000000002"}]}}]
    }

    result = provider.lookup("9780306406157")

    assert result.status == "No data"
    assert result.failure_kind == "unverified"
    assert result.values == {}


def test_google_books_distinguishes_empty_results_from_unverified_volumes():
    provider = GoogleBooksProvider()
    provider._request_json = lambda _url: {"totalItems": 0}
    no_match = provider.lookup("9780385504201")
    assert no_match.status == "No data"
    assert no_match.record_found is False
    assert no_match.failure_kind is None

    def response(url):
        query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["q"][0]
        if query == "9780385504201":
            return {"totalItems": 1, "items": [{"volumeInfo": {
                "title": "Returned candidate", "industryIdentifiers": [
                    {"type": "ISBN_13", "identifier": "9780000000002"}
                ],
            }}]}
        return {"totalItems": 0}

    provider._request_json = response
    unverified = provider.lookup("9780385504201")
    assert unverified.status == "No data"
    assert unverified.record_found is False
    assert unverified.failure_kind == "unverified"

    provider._request_json = lambda url: (
        {"totalItems": 1, "items": [{"volumeInfo": {"title": "Candidate without identifiers"}}]}
        if urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["q"][0] == "9780385504201"
        else {"totalItems": 0}
    )
    missing_identifiers = provider.lookup("9780385504201")
    assert missing_identifiers.failure_kind == "unverified"


def test_google_books_reports_malformed_total_items_as_unexpected_response():
    provider = GoogleBooksProvider()
    provider._request_json = lambda _url: {"totalItems": "many", "items": []}

    result = provider.lookup("9780385504201")

    assert result.status == "Lookup failed"
    assert result.failure_kind == "unexpected"


def test_google_books_api_key_is_optional_and_only_added_when_configured():
    provider = GoogleBooksProvider("private-test-key")
    requested = []
    provider._request_json = lambda url: (requested.append(url) or {"items": []})
    assert provider.lookup("9780306406157").status == "No data"
    assert urllib.parse.parse_qs(urllib.parse.urlparse(requested[0]).query)["key"] == ["private-test-key"]
    requested.clear()
    no_key = GoogleBooksProvider()
    no_key._request_json = lambda url: (requested.append(url) or {"items": []})
    no_key.lookup("9780306406157")
    no_key_queries = [urllib.parse.parse_qs(urllib.parse.urlparse(url).query) for url in requested]
    assert len(no_key_queries) == 3
    assert all("key" not in query for query in no_key_queries)


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


def test_lookup_service_keeps_google_unverified_result_distinct_from_no_match():
    primary = StubProvider("Open Library", MetadataResult("No data", {}, "Open Library", record_found=False))
    fallback = StubProvider("Google Books", MetadataResult(
        "No data", {}, "Google Books", "unverified internal diagnostic", "unverified", record_found=False
    ))

    result = MetadataLookupService((primary, fallback)).lookup("9780385504201")

    assert result.status == "No data"
    assert result.failure_kind == "unverified"
    assert result.provider_statuses == {
        "Open Library": "No matching record",
        "Google Books": "Results returned · ISBN not confirmed",
    }


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


def test_google_books_description_enriches_open_library_title_without_overwriting_it():
    primary = StubProvider("Open Library", MetadataResult(
        "Retrieved", {"title": "Primary title", "author": "Primary author"}, "Open Library", record_found=True
    ))
    fallback = StubProvider("Google Books", MetadataResult(
        "Retrieved", {"title": "Fallback title", "book_details": "Full description"}, "Google Books", record_found=True
    ))

    result = MetadataLookupService((primary, fallback)).lookup("9780306406157")

    assert result.values["title"] == "Primary Title"
    assert result.values["author"] == "Primary author"
    assert result.values["book_details"] == "Full description"


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
