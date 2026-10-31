from __future__ import annotations

import json
import urllib.error
import urllib.parse

import pytest

from bookledger.provider_registry import DEFAULT_PROVIDER_IDS, PROVIDER_REGISTRY, build_providers
from bookledger.provider_settings import ProviderSettings
from bookledger.services.archive_org import ArchiveOrgProvider
from bookledger.services.metadata import MetadataLookupService, MetadataResult


ISBN = "9780553290998"
REPRODUCTION_BOOKS = {
    "9780385504201": ("The Da Vinci Code", "Dan Brown", "A historical mystery thriller. " * 4),
    "9780199558292": ("Alice's Adventures in Wonderland", "Lewis Carroll", "A girl follows a rabbit. " * 5),
    "9780553290998": ("Nightfall", "Isaac Asimov", "A story about a world with one sunset. " * 4),
}


def document(identifier, title, *, creator=None, publisher=None, year=None, edition=None, description=None):
    result = {"identifier": identifier, "title": title}
    for key, value in (
        ("creator", creator), ("publisher", publisher), ("year", year),
        ("edition", edition), ("description", description),
    ):
        if value is not None:
            result[key] = value
    return result


def search_payload(*documents):
    return {"response": {"docs": list(documents)}}


def verified_isbns(*values):
    return {"metadata": {"isbn": list(values)}}


def test_registry_and_fresh_defaults_put_archive_between_google_and_booktopia():
    assert DEFAULT_PROVIDER_IDS == ("open_library", "google_books", "archive_org", "booktopia")
    assert [item.name for item in PROVIDER_REGISTRY if item.implemented] == [
        "Open Library", "Google Books", "Archive.org", "Booktopia",
    ]
    settings = ProviderSettings.defaults()
    assert [provider.name for provider in build_providers(settings)] == [
        "Open Library", "Google Books", "Archive.org", "Booktopia",
    ]


def test_successful_single_search_result_maps_fields_and_requests_only_needed_columns():
    provider = ArchiveOrgProvider()
    requested = []
    provider._request_json = lambda url: (
        requested.append(url) or search_payload(document(
            "nightfall-1991", "Nightfall", creator=["Isaac Asimov", "Editor"],
            publisher="Doubleday", year="1991-01-01", edition="First edition",
            description="An unusually long and useful book description. " * 4,
        ))
    )

    result = provider.lookup(ISBN)

    query = urllib.parse.parse_qs(urllib.parse.urlparse(requested[0]).query)
    assert query["q"] == [f"isbn:{ISBN}"]
    assert query["rows"] == ["10"]
    assert query["output"] == ["json"]
    assert query["fl[]"] == ["identifier", "title", "creator", "publisher", "year", "edition", "description"]
    assert "isbn" not in query["fl[]"]
    assert len(requested) == 1
    assert result.status == "Retrieved"
    assert result.source == "Archive.org (nightfall-1991)"
    assert result.values == {
        "title": "Nightfall", "author": "Isaac Asimov", "publisher": "Doubleday",
        "publication_year": 1991, "edition": "First edition",
        "book_details": " ".join(("An unusually long and useful book description. " * 4).split()),
    }


def test_ambiguous_search_verifies_records_and_selects_exact_isbn_match():
    provider = ArchiveOrgProvider()
    calls = []
    docs = search_payload(
        document(
            "unrelated-record", "Nightfall Collection", creator="Archive contributor",
            publisher="Wrong Press", year=1950, edition="Collected catalog",
            description="A comprehensive catalog record unrelated to the requested novel. " * 5,
        ),
        document("matching-edition", "Nightfall", creator="Isaac Asimov", publisher="Gnome Press", year=1951),
    )

    def request(url):
        calls.append(url)
        if "advancedsearch.php" in url:
            return docs
        if url.endswith("unrelated-record"):
            return verified_isbns("9780000000002")
        return verified_isbns(ISBN)

    provider._request_json = request
    result = provider.lookup(ISBN)

    assert len(calls) == 3
    assert calls[1].endswith("/metadata/unrelated-record")
    assert calls[2].endswith("/metadata/matching-edition")
    assert result.values == {
        "title": "Nightfall", "author": "Isaac Asimov", "publisher": "Gnome Press",
        "publication_year": 1951,
    }
    assert result.source == "Archive.org (matching-edition)"


def test_individual_record_verification_accepts_valid_isbn10_alias():
    provider = ArchiveOrgProvider()
    provider._request_json = lambda url: (
        search_payload(
            document("nightfall-a", "Nightfall: Edition A", creator="Isaac Asimov"),
            document("nightfall-b", "Nightfall: Edition B", creator="Isaac Asimov", publisher="Doubleday"),
        ) if "advancedsearch.php" in url else verified_isbns("0385504209")
    )

    result = provider.lookup("9780385504201")

    assert result.status == "Retrieved"
    assert result.source.startswith("Archive.org (nightfall-")


def test_duplicate_search_rows_for_same_identifier_use_one_coherent_record():
    provider = ArchiveOrgProvider()
    calls = []
    provider._request_json = lambda _url: (
        calls.append(_url) or search_payload(
            document("nightfall-record", "Nightfall", creator="Isaac Asimov", publisher="Doubleday", year=1991),
            document(
                "nightfall-record", "Nightfall", creator="Isaac Asimov", publisher="Doubleday", year=1991,
                description="A useful description of this edition and the story. " * 3,
            ),
        )
    )

    result = provider.lookup(ISBN)

    assert len(calls) == 1
    assert result.values == {
        "title": "Nightfall", "author": "Isaac Asimov", "publisher": "Doubleday",
        "publication_year": 1991,
        "book_details": " ".join(("A useful description of this edition and the story. " * 3).split()),
    }


def test_missing_or_irrelevant_titles_are_rejected_and_missing_optional_fields_are_allowed():
    provider = ArchiveOrgProvider()
    provider._request_json = lambda _url: search_payload(
        document("missing-title", None, creator="Author", publisher="Press"),
        document("admin-title", "Internet Archive collection", creator="Cataloger"),
        document("book-without-options", "The Ascent of Mind"),
    )

    result = provider.lookup("9780553070842")

    assert result.status == "Retrieved"
    assert result.values == {"title": "The Ascent of Mind"}


def test_malformed_year_and_short_description_are_omitted():
    provider = ArchiveOrgProvider()
    provider._request_json = lambda _url: search_payload(document(
        "partial", "A Valid Book", creator=["A. Author", "B. Editor"],
        year="not-a-year", description="A short note.",
    ))

    result = provider.lookup(ISBN)

    assert result.values == {"title": "A Valid Book", "author": "A. Author"}


def test_no_matching_results_returns_no_data():
    provider = ArchiveOrgProvider()
    provider._request_json = lambda _url: search_payload()
    result = provider.lookup(ISBN)
    assert result.status == "No data"
    assert result.record_found is False


@pytest.mark.parametrize("isbn", tuple(REPRODUCTION_BOOKS))
def test_reproduction_isbns_direct_archive_adapter_with_controlled_search(isbn):
    title, author, description = REPRODUCTION_BOOKS[isbn]
    provider = ArchiveOrgProvider()
    provider._request_json = lambda _url: search_payload(document(
        f"record-{isbn[-4:]}", title, creator=author, description=description,
    ))

    result = provider.lookup(isbn)

    assert result.status == "Retrieved"
    assert result.record_found is True
    assert result.values["title"].casefold() == title.casefold()
    assert result.values["author"] == author
    assert result.values["book_details"]


@pytest.mark.parametrize("payload", [None, [], {"response": []}, {"response": {"docs": "bad"}}])
def test_malformed_search_responses_are_reported(payload):
    provider = ArchiveOrgProvider()
    provider._request_json = lambda _url: payload
    result = provider.lookup(ISBN)
    assert result.status == "Lookup failed"
    assert result.failure_kind == "unexpected"


@pytest.mark.parametrize(
    ("exception", "kind"),
    [
        (urllib.error.HTTPError("https://archive.org", 503, "unavailable", {}, None), "provider"),
        (TimeoutError("slow"), "timeout"),
        (ConnectionError("offline"), "network"),
        (json.JSONDecodeError("bad JSON", "{", 0), "unexpected"),
    ],
)
def test_http_timeout_network_and_malformed_json_failures_are_classified(exception, kind):
    provider = ArchiveOrgProvider()
    provider._request_json = lambda _url: (_ for _ in ()).throw(exception)
    result = provider.lookup(ISBN)
    assert result.status == "Lookup failed"
    assert result.failure_kind == kind


def test_ambiguous_records_without_an_exact_individual_isbn_match_are_not_guessed():
    provider = ArchiveOrgProvider()
    provider._request_json = lambda url: (
        search_payload(
            document("nightfall-a", "Nightfall", creator="Isaac Asimov"),
            document("nightfall-b", "Nightfall: Another Edition", creator="Another Contributor", publisher="Another Press"),
        ) if "advancedsearch.php" in url else verified_isbns("9780000000002")
    )

    result = provider.lookup(ISBN)

    assert result.status == "No data"
    assert result.failure_kind == "unverified"
    assert not result.values


def test_alternate_editions_with_same_title_and_author_are_verified_separately():
    provider = ArchiveOrgProvider()
    calls = []
    provider._request_json = lambda url: (
        calls.append(url) or (
            search_payload(
                document("wrong-edition", "Nightfall", creator="Isaac Asimov", publisher="Old Press", year=1980),
                document("requested-edition", "Nightfall", creator="Isaac Asimov", publisher="Right Press", year=1991),
            ) if "advancedsearch.php" in url
            else verified_isbns("9780000000002") if url.endswith("wrong-edition")
            else verified_isbns(ISBN)
        )
    )

    result = provider.lookup(ISBN)

    assert result.source == "Archive.org (requested-edition)"
    assert result.values["publisher"] == "Right Press"
    assert len(calls) == 3


def test_multiple_candidates_are_not_field_merged():
    provider = ArchiveOrgProvider()
    provider._request_json = lambda url: (
        search_payload(
            document("first", "Nightfall", creator="Isaac Asimov", publisher="First Press"),
            document("second", "Nightfall: A Different Edition", creator="Isaac Asimov", year=1998),
        ) if "advancedsearch.php" in url else verified_isbns(ISBN)
    )

    result = provider.lookup(ISBN)

    assert result.values == {"title": "Nightfall", "author": "Isaac Asimov", "publisher": "First Press"}


def test_archive_org_timeout_applies_to_every_request_using_remaining_budget(monkeypatch):
    provider = ArchiveOrgProvider()
    timeouts = []
    monkeypatch.setattr(provider, "_request_timeout", lambda: timeouts.append(5.0) or 5.0)
    response = type("Response", (), {
        "__enter__": lambda self: self,
        "__exit__": lambda self, *_args: None,
        "read": lambda self, _limit: b'{"response":{"docs":[]}}',
    })()
    from unittest.mock import patch
    with patch("bookledger.services.archive_org.urllib.request.urlopen", return_value=response) as opener:
        provider._request_json("https://archive.org/advancedsearch.php")
    assert opener.call_args.kwargs["timeout"] == 5.0
    assert timeouts == [5.0]


def test_search_and_item_verification_share_one_five_second_deadline(monkeypatch):
    from bookledger.services import metadata_contract

    provider = ArchiveOrgProvider()
    clock = iter((0.0, 1.0, 2.0, 3.0))
    monkeypatch.setattr(metadata_contract.time, "monotonic", lambda: next(clock))
    timeouts = []

    def request(url):
        timeouts.append(provider._request_timeout())
        return search_payload(
            document("a", "Nightfall A", creator="Isaac Asimov"),
            document("b", "Nightfall B", creator="Isaac Asimov", publisher="Press"),
        ) if "advancedsearch.php" in url else verified_isbns(ISBN)

    provider._request_json = request
    result = provider.lookup(ISBN)

    assert timeouts == [4.0, 3.0]
    assert result.duration_seconds == 3.0


def test_provider_failure_does_not_stop_later_providers():
    archive = ArchiveOrgProvider()
    archive._request_json = lambda _url: (_ for _ in ()).throw(TimeoutError("timeout"))

    class LaterProvider:
        name = "Later"

        def lookup(self, _isbn):
            return MetadataResult("Retrieved", {"title": "Fallback title"}, self.name)

    result = MetadataLookupService((archive, LaterProvider())).lookup(ISBN)
    assert result.values["title"] == "Fallback Title"
    assert result.provider_statuses["Archive.org"] == "Timed out"


@pytest.mark.parametrize("isbn", tuple(REPRODUCTION_BOOKS))
def test_reproduction_isbns_through_normal_ordered_provider_chain(isbn):
    title, author, description = REPRODUCTION_BOOKS[isbn]
    archive = ArchiveOrgProvider()
    archive._request_json = lambda _url: search_payload(document(
        f"record-{isbn[-4:]}", title, creator=author, description=description,
    ))

    class NoMatchProvider:
        def __init__(self, name):
            self.name = name

        def lookup(self, _isbn):
            return MetadataResult("No data", {}, self.name, record_found=False)

    providers = (
        NoMatchProvider("Open Library"),
        NoMatchProvider("Google Books"),
        archive,
        NoMatchProvider("Booktopia"),
    )
    result = MetadataLookupService(providers).lookup(isbn)

    assert [provider.name for provider in providers] == [
        "Open Library", "Google Books", "Archive.org", "Booktopia",
    ]
    assert result.status == "Retrieved"
    assert result.source.startswith("Archive.org (")
    assert result.values["title"].casefold() == title.casefold()
    assert result.provider_statuses["Archive.org"] == "Metadata retrieved · some fields missing"


def test_alice_intake_can_be_partial_when_archive_search_has_no_candidate():
    archive = ArchiveOrgProvider()
    archive._request_json = lambda _url: search_payload()

    class OpenLibraryRecord:
        name = "Open Library"

        def lookup(self, _isbn):
            return MetadataResult("Retrieved", {
                "title": "Alice's Adventures in Wonderland", "author": "Lewis Carroll",
                "publication_year": 1865,
            }, self.name, record_found=True)

    class NoMatchProvider:
        def __init__(self, name):
            self.name = name

        def lookup(self, _isbn):
            return MetadataResult("No data", {}, self.name, record_found=False)

    result = MetadataLookupService((
        OpenLibraryRecord(), NoMatchProvider("Google Books"), archive,
        NoMatchProvider("Booktopia"),
    )).lookup("9780199558292")

    assert result.status == "Retrieved"
    assert result.source == "Open Library"
    assert "book_details" not in result.values
    assert result.provider_statuses["Archive.org"] == "No matching record"

