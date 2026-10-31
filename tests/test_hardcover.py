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
        "description": "Edition synopsis.", "publisher": {"name": "Example Press"},
        "book": {"title": "The Book", "author_names": ["A. Writer"], "description": "Book synopsis.", "release_year": 2010, "genres": ["Fantasy"]},
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
    assert request.get_header("Authorization") == "private-secret-value"
    assert "private-secret-value" not in request.data.decode("utf-8")
    assert "isbn_13" in body["query"] and "isbn_10" in body["query"]
    assert body["variables"] == {"isbn10": ISBN10, "isbn13": ISBN13}
    assert captured["timeout"] <= 5
    assert result.values == {
        "title": "The Book", "author": "A. Writer", "isbn": ISBN13,
        "genre": "Fantasy",
        "publisher": "Example Press", "publication_year": 2012, "edition": "Revised edition",
        "page_count": 320, "book_details": "Edition synopsis.",
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
    [(401, "authentication"), (403, "authorization"), (404, "provider"), (429, "rate_limit"), (500, "provider")],
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
        description=None, publisher=None,
        book={"title": "", "author_names": ["Writer One", "Writer Two"], "description": "Book description", "release_date": "2008", "genres": []},
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
