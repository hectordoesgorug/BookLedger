from __future__ import annotations

import json
import urllib.error

import pytest

from bookledger.services.bigbook import BigbookProvider


ISBN13 = "9780306406157"
ISBN10 = "0306406152"


def test_bigbook_searches_isbn13_with_header_and_verifies_details(monkeypatch):
    calls = []
    search = {"books": [[{"id": 17, "title": "Search title"}]]}
    details = {
        "id": 17, "title": "A Book", "identifiers": {"isbn_10": ISBN10, "isbn_13": ISBN13},
        "authors": [{"name": "A. Writer"}], "publish_date": "2001-03-04",
        "number_of_pages": 321.0, "description": "A useful description.",
    }

    def request(url, headers):
        calls.append((url, headers))
        return search if "search-books" in url else details

    provider = BigbookProvider("private-key")
    monkeypatch.setattr(provider, "_request_json_with_headers", request)
    result = provider.lookup(ISBN10)

    assert len(calls) == 2
    assert "isbn=9780306406157" in calls[0][0]
    assert "private-key" not in calls[0][0]
    assert calls[0][1] == {"x-api-key": "private-key"}
    assert result.values == {
        "title": "A Book", "author": "A. Writer", "isbn": ISBN13,
        "book_details": "A useful description.", "publication_year": 2001, "page_count": 321,
    }
    assert result.record_found is True


def test_bigbook_tries_candidates_until_an_equivalent_isbn_matches(monkeypatch):
    details_by_id = {
        "1": {"identifiers": {"isbn_13": "9780000000002"}, "title": "Wrong"},
        "2": {"identifiers": {"isbn_10": ISBN10}, "title": "Right"},
    }
    provider = BigbookProvider("key")
    monkeypatch.setattr(provider, "_request_json_with_headers", lambda url, _headers: (
        {"books": [[{"id": 1}, {"id": 2}]]} if "search-books" in url else details_by_id[url.rsplit("/", 1)[-1]]
    ))
    result = provider.lookup(ISBN13)
    assert result.values["title"] == "Right"
    assert result.values["isbn"] == ISBN13


def test_bigbook_does_not_accept_unverified_candidates(monkeypatch):
    provider = BigbookProvider("key")
    monkeypatch.setattr(provider, "_request_json_with_headers", lambda url, _headers: (
        {"books": [[{"id": 1}]]} if "search-books" in url
        else {"identifiers": {"isbn_13": "9780000000002"}, "title": "Unrelated"}
    ))
    result = provider.lookup(ISBN13)
    assert result.status == "No data"
    assert result.failure_kind == "unverified"
    assert result.values == {}


def test_bigbook_missing_key_empty_and_malformed_responses(monkeypatch):
    assert BigbookProvider().lookup(ISBN13).failure_kind == "authentication"

    provider = BigbookProvider("key")
    monkeypatch.setattr(provider, "_request_json_with_headers", lambda *_args: {"books": []})
    assert provider.lookup(ISBN13).record_found is False
    monkeypatch.setattr(provider, "_request_json_with_headers", lambda *_args: [])
    assert provider.lookup(ISBN13).failure_kind == "unexpected"


@pytest.mark.parametrize(("status", "failure_kind"), [(401, "authentication"), (403, "authorization"), (402, "quota"), (429, "rate_limit")])
def test_bigbook_classifies_quota_and_rate_limit(status, failure_kind, monkeypatch):
    provider = BigbookProvider("private-secret-value")

    def fail(*_args):
        raise urllib.error.HTTPError("https://api.bigbookapi.com/search-books", status, "failure", {}, None)

    monkeypatch.setattr(provider, "_request_json_with_headers", fail)
    result = provider.lookup(ISBN13)
    assert result.failure_kind == failure_kind
    assert "private-secret-value" not in str(result.error)


def test_bigbook_network_failure_and_timeout_are_preserved(monkeypatch):
    provider = BigbookProvider("key")
    monkeypatch.setattr(provider, "_request_json_with_headers", lambda *_args: (_ for _ in ()).throw(TimeoutError("timed out")))
    assert provider.lookup(ISBN13).failure_kind == "timeout"


@pytest.mark.parametrize(("status", "kind"), [(401, "authentication"), (403, "authorization"), (402, "quota"), (429, "rate_limit")])
def test_bigbook_classifies_quota_and_rate_limit_during_detail_fetch(status, kind, monkeypatch):
    provider = BigbookProvider("key")

    def request(url, _headers):
        if "search-books" in url:
            return {"books": [[{"id": 1}]]}
        raise urllib.error.HTTPError(url, status, "failure", {}, None)

    monkeypatch.setattr(provider, "_request_json_with_headers", request)
    result = provider.lookup(ISBN13)
    assert result.failure_kind == kind

