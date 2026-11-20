from __future__ import annotations

import json
import urllib.error

import pytest

from bookledger.services.hardcover import HARDCOVER_ENDPOINT, HardcoverProvider


ISBN13 = "9780547928227"
ISBN10 = "054792822X"


class Response:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.payload


def matching_edition(**changes):
    edition = {
        "id": 12, "title": "The Edition Title", "subtitle": None,
        "isbn_10": ISBN10, "isbn_13": ISBN13, "pages": 320,
        "release_date": "2012-10-18", "release_year": None,
        "edition_format": "Paperback", "edition_information": "Revised edition",
        "publisher": {"name": "Example Press"},
        "contributions": [{"contribution": "Author", "author": {"name": "A. Writer"}}],
        "book": {"title": "The Book", "contributions": [{"contribution": "Author", "author": {"name": "A. Writer"}}], "description": "Book synopsis.", "release_year": 2010, "cached_tags": {"Genre": [{"tag": "Fantasy"}]}},
    }
    edition.update(changes)
    return edition


def test_hardcover_queries_both_isbn_forms_and_maps_verified_edition(monkeypatch):
    captured = {}

    def urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return Response({"data": {"byIsbn13": [matching_edition()], "byIsbn10": []}})

    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    provider = HardcoverProvider("private-secret-value")
    result = provider.lookup(ISBN13)

    request = captured["request"]
    body = json.loads(request.data)
    assert request.full_url == HARDCOVER_ENDPOINT
    assert request.get_header("Authorization") == "Bearer private-secret-value"
    assert "private-secret-value" not in request.data.decode("utf-8")
    assert "isbn_13" in body["query"] and "isbn_10" in body["query"]
    assert "author_names" not in body["query"] and "genres" not in body["query"]
    assert "contributions" in body["query"] and "cached_tags" in body["query"]
    assert body["query"].count("description") == 2  # Only the two book selections.
    assert body["variables"] == {"isbn10": ISBN10, "isbn13": ISBN13}
    assert captured["timeout"] <= 5
    assert result.values == {
        "title": "The Edition Title", "author": "A. Writer", "isbn": ISBN13,
        "genre": "Fantasy",
        "publisher": "Example Press", "publication_year": 2012, "edition": "Revised edition",
        "page_count": 320, "book_details": "Book synopsis.",
    }
    assert result.record_found is True


def test_hardcover_accepts_only_exact_isbn_edition(monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen", lambda *_args, **_kwargs: Response({
        "data": {"byIsbn13": [matching_edition(isbn_13="9780000000002", isbn_10="0000000000")], "byIsbn10": []},
    }))
    result = HardcoverProvider("token").lookup(ISBN13)
    assert result.status == "No data"
    assert result.failure_kind == "unverified"
    assert not result.values


def test_hardcover_missing_token_no_match_graphql_errors_and_invalid_json(monkeypatch):
    assert HardcoverProvider().lookup(ISBN13).failure_kind == "authentication"
    monkeypatch.setattr("urllib.request.urlopen", lambda *_args, **_kwargs: Response({"data": {"byIsbn13": [], "byIsbn10": []}}))
    assert HardcoverProvider("token").lookup(ISBN13).record_found is False

    monkeypatch.setattr("urllib.request.urlopen", lambda *_args, **_kwargs: Response({"errors": [{"message": "private resolver detail"}]}))
    result = HardcoverProvider("token").lookup(ISBN13)
    assert result.failure_kind == "provider"
    assert result.error == "Hardcover GraphQL request failed."
    assert "private resolver detail" not in result.error

    class InvalidJson(Response):
        def read(self):
            return b"{broken"

    monkeypatch.setattr("urllib.request.urlopen", lambda *_args, **_kwargs: InvalidJson({}))
    assert HardcoverProvider("token").lookup(ISBN13).failure_kind == "unexpected"


@pytest.mark.parametrize(
    ("status", "kind"),
    [(401, "authentication"), (402, "provider"), (403, "authorization"), (404, "provider"), (429, "rate_limit"), (500, "provider"), (503, "provider")],
)
def test_hardcover_classifies_http_errors(status, kind, monkeypatch):
    def fail(*_args, **_kwargs):
        raise urllib.error.HTTPError(HARDCOVER_ENDPOINT, status, "failure", {}, None)

    monkeypatch.setattr("urllib.request.urlopen", fail)
    result = HardcoverProvider("private-secret-value").lookup(ISBN13)
    assert result.failure_kind == kind
    assert "private-secret-value" not in str(result.error)


def test_hardcover_maps_fallback_metadata_and_timeout(monkeypatch):
    edition = matching_edition(
        title="Edition title", edition_information=None, edition_format="Large print",
        contributions=[], publisher=None,
        book={"title": "", "contributions": [{"contribution": "Author", "author": {"name": name}} for name in ("Writer One", "Writer Two")], "description": "Book description", "release_date": "2008", "cached_tags": {}},
    )
    edition["isbn_13"] = None
    monkeypatch.setattr("urllib.request.urlopen", lambda *_args, **_kwargs: Response({"data": {"byIsbn13": [], "byIsbn10": [edition]}}))
    result = HardcoverProvider("token").lookup(ISBN13)
    assert result.values["title"] == "Edition title"
    assert result.values["author"] == "Writer One, Writer Two"
    assert result.values["edition"] == "Large print"
    assert result.values["publication_year"] == 2012
    assert result.values["book_details"] == "Book description"

    monkeypatch.setattr("urllib.request.urlopen", lambda *_args, **_kwargs: (_ for _ in ()).throw(TimeoutError("timed out")))
    assert HardcoverProvider("token").lookup(ISBN13).failure_kind == "timeout"


@pytest.mark.parametrize("token", ["private-token", "Bearer private-token", "bearer private-token"])
def test_hardcover_accepts_saved_bare_and_prefixed_tokens(token, monkeypatch):
    def request(req, **_kwargs):
        assert req.get_header("Authorization") == "Bearer private-token"
        return Response({"data": {"byIsbn13": [], "byIsbn10": []}})
    monkeypatch.setattr("urllib.request.urlopen", request)
    assert HardcoverProvider(token).lookup(ISBN10).status == "No data"


def test_hardcover_maps_only_author_roles_and_prefers_edition_contributions(monkeypatch):
    edition = matching_edition(contributions=[
        {"contribution": "Translator", "author": {"name": "Translator"}},
        {"contribution": "Author", "author": {"name": "Edition Author"}},
        {"contribution": "Author", "author": {"name": "Edition Author"}},
        {"contribution": "Editor", "author": {"name": "Editor"}},
    ])
    monkeypatch.setattr("urllib.request.urlopen", lambda *_args, **_kwargs: Response({"data": {"byIsbn13": [edition]}}))
    assert HardcoverProvider("token").lookup(ISBN13).values["author"] == "Edition Author"


@pytest.mark.parametrize("book", [None, {}, {"contributions": [None, {"author": {"name": "Unknown role"}}], "cached_tags": {"Mood": [{"tag": "Happy"}]}}])
def test_hardcover_missing_optional_metadata_is_not_fabricated(book, monkeypatch):
    edition = matching_edition(book=book, contributions=None, publisher=None)
    monkeypatch.setattr("urllib.request.urlopen", lambda *_args, **_kwargs: Response({"data": {"byIsbn13": [edition]}}))
    result = HardcoverProvider("token").lookup(ISBN13)
    assert result.status == "Retrieved"
    for field in ("author", "publisher", "genre", "book_details"):
        assert result.values[field] is None


@pytest.mark.parametrize("payload", [[], {}, {"data": {}}, {"data": {"byIsbn13": None}}, {"data": {"byIsbn13": [None]}}, {"errors": {"message": "secret"}}])
def test_hardcover_rejects_malformed_responses(payload, monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen", lambda *_args, **_kwargs: Response(payload))
    assert HardcoverProvider("token").lookup(ISBN13).failure_kind == "unexpected"


@pytest.mark.parametrize("message,code,kind", [
    ("expired token secret", "", "authentication"),
    ("Unable to verify JWT", "invalid-jwt", "authentication"),
    ("secret", "insufficient_scope", "authorization"),
    ("Access denied secret", "", "authorization"),
    ("rate limit secret", "", "rate_limit"),
    ("field not found secret", "validation-failed", "provider"),
])
def test_hardcover_graphql_errors_are_classified_and_sanitized(message, code, kind, monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen", lambda *_args, **_kwargs: Response({
        "errors": [{"message": message, "extensions": {"code": code}}],
    }))
    result = HardcoverProvider("secret").lookup(ISBN13)
    assert result.failure_kind == kind
    assert "secret" not in result.error
