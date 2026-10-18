from __future__ import annotations

import json

from bookledger.paths import AppPaths
from bookledger.provider_registry import DEFAULT_PROVIDER_IDS, build_providers
from bookledger.provider_settings import ProviderSettings, ProviderSettingsStore
from bookledger.services.lifecycle import CopyLifecycleService
from bookledger.services.metadata import MetadataLookupService, MetadataResult


def test_absent_provider_configuration_loads_defaults(tmp_path):
    store = ProviderSettingsStore(tmp_path / "config.json", tmp_path / "fallback" / "config.json")
    settings = store.load()
    assert settings.order == list(DEFAULT_PROVIDER_IDS)
    assert settings.ordered_enabled_ids() == list(DEFAULT_PROVIDER_IDS)


def test_provider_order_and_enabled_state_round_trip_and_preserve_unrelated_fields(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"unrelated": {"keep": True}, "version": 1}), encoding="utf-8")
    store = ProviderSettingsStore(path, tmp_path / "fallback.json")
    settings = ProviderSettings.defaults()
    settings.order = ["booktopia", "open_library", "google_books"]
    settings.enabled["google_books"] = False
    store.save(settings)
    reloaded = store.load()
    assert reloaded.order == settings.order
    assert reloaded.enabled["google_books"] is False
    assert json.loads(path.read_text(encoding="utf-8"))["unrelated"] == {"keep": True}


def test_incomplete_configuration_uses_safe_defaults_for_missing_providers(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"version": 1, "metadata_providers": {"enabled": {"google_books": False}}}), encoding="utf-8")
    settings = ProviderSettingsStore(path, tmp_path / "fallback.json").load()
    assert settings.order == list(DEFAULT_PROVIDER_IDS)
    assert settings.enabled == {"open_library": True, "google_books": False, "booktopia": True}


def test_malformed_configuration_is_preserved_and_defaults_are_reported(tmp_path):
    path = tmp_path / "config.json"
    original = "{broken"
    path.write_text(original, encoding="utf-8")
    store = ProviderSettingsStore(path, tmp_path / "fallback.json")
    assert store.load().order == list(DEFAULT_PROVIDER_IDS)
    assert "preserved" in store.warning
    store.save(ProviderSettings.defaults())
    assert path.read_text(encoding="utf-8") == original
    assert store.fallback_path.is_file()


def test_malformed_portable_config_falls_back_to_valid_user_config(tmp_path):
    portable = tmp_path / "config.json"
    fallback = tmp_path / "profile" / "config.json"
    portable.write_text("{broken", encoding="utf-8")
    fallback.parent.mkdir()
    fallback.write_text(json.dumps({"metadata_providers": {"enabled": {"booktopia": False}}}), encoding="utf-8")
    store = ProviderSettingsStore(portable, fallback)
    settings = store.load()
    assert settings.enabled["booktopia"] is False
    assert "preserved" in store.warning
    assert store.active_path == fallback


def test_read_only_portable_root_saves_to_per_user_fallback(tmp_path, monkeypatch):
    portable = tmp_path / "config.json"
    fallback = tmp_path / "profile" / "config.json"
    store = ProviderSettingsStore(portable, fallback)
    store.load()
    original_write = ProviderSettingsStore._atomic_write

    def write_with_read_only_root(path, document):
        if path == portable:
            raise OSError("read-only")
        return original_write(path, document)

    monkeypatch.setattr(ProviderSettingsStore, "_atomic_write", staticmethod(write_with_read_only_root))
    assert store.save(ProviderSettings.defaults()) == fallback
    assert fallback.is_file()
    assert not portable.exists()


def test_disabled_booktopia_is_not_queried_for_a_missing_synopsis(monkeypatch):
    from bookledger.services.booktopia import BooktopiaProvider
    from bookledger.services.metadata import GoogleBooksProvider, OpenLibraryProvider

    called = []
    def fake_lookup(self, _isbn):
        called.append(self.name)
        if self.name == "Open Library":
            return MetadataResult("Retrieved", {
                "title": "Book", "author": "Author", "genre": "Fiction",
                "publisher": "Press", "publication_year": 2020,
            }, self.name)
        return MetadataResult("No data", {}, self.name)

    for provider_type in (OpenLibraryProvider, GoogleBooksProvider, BooktopiaProvider):
        monkeypatch.setattr(provider_type, "lookup", fake_lookup)
    settings = ProviderSettings.defaults()
    settings.enabled["booktopia"] = False
    providers = build_providers(settings)
    assert [provider.name for provider in providers] == ["Open Library", "Google Books"]
    MetadataLookupService(providers).lookup("9780306406157")
    assert called == ["Open Library", "Google Books"]


def test_configured_order_controls_lookup_order_and_merges_only_empty_fields():
    class Stub:
        def __init__(self, name, values, calls):
            self.name, self.values, self.calls = name, values, calls

        def lookup(self, _isbn):
            self.calls.append(self.name)
            return MetadataResult("Retrieved", self.values, self.name)

    calls = []
    providers = (Stub("Booktopia", {"title": "Later title", "author": "Author", "publisher": "Press"}, calls),
                 Stub("Google Books", {"title": "Another title", "book_details": "Synopsis"}, calls))
    result = MetadataLookupService(providers).lookup("9780306406157")
    assert calls == ["Booktopia", "Google Books"]
    assert result.values["title"] == "Later Title"
    assert result.values["publisher"] == "Press"
    assert result.values["book_details"] == "Synopsis"


def test_reordering_registry_changes_actual_lookup_order(monkeypatch):
    from bookledger.services.booktopia import BooktopiaProvider
    from bookledger.services.metadata import GoogleBooksProvider, OpenLibraryProvider

    calls = []
    def fake_lookup(self, _isbn):
        calls.append(self.name)
        values = {"title": "Book"} if self.name == "Booktopia" else {
            "author": "Author", "genre": "History", "publisher": "Press", "publication_year": 2020,
        } if self.name == "Google Books" else {}
        return MetadataResult("Retrieved" if values else "No data", values, self.name)

    for provider_type in (OpenLibraryProvider, GoogleBooksProvider, BooktopiaProvider):
        monkeypatch.setattr(provider_type, "lookup", fake_lookup)
    settings = ProviderSettings.defaults()
    settings.order = ["booktopia", "google_books", "open_library"]
    result = MetadataLookupService(build_providers(settings)).lookup("9780306406157")
    assert calls == ["Booktopia", "Google Books"]
    assert result.values["title"] == "Book"
    assert result.values["author"] == "Author"


def test_lookup_continues_after_failure_and_stops_after_synopsis_completion():
    class Stub:
        def __init__(self, name, result, calls):
            self.name, self.result, self.calls = name, result, calls

        def lookup(self, _isbn):
            self.calls.append(self.name)
            return self.result

    calls = []
    first = Stub("Open Library", MetadataResult("Lookup failed", {}, "Open Library", "offline", "network"), calls)
    second = Stub("Google Books", MetadataResult("Retrieved", {
        "title": "A Book", "author": "An Author", "genre": "History", "publisher": "Press",
        "publication_year": 2020, "edition": "First", "page_count": 300,
    }, "Google Books"), calls)
    third = Stub("Booktopia", MetadataResult("Retrieved", {"book_details": "Optional synopsis"}, "Booktopia"), calls)
    result = MetadataLookupService((first, second, third)).lookup("9780306406157")
    assert calls == ["Open Library", "Google Books", "Booktopia"]
    assert result.values["title"] == "A Book"
    assert result.values["page_count"] == 300
    assert result.values["book_details"] == "Optional synopsis"
    assert result.provider_statuses["Open Library"] == "Connection failed"


def test_inventory_purge_does_not_remove_root_provider_configuration(tmp_path):
    paths = AppPaths(tmp_path)
    paths.prepare(migrate_profile_config=False)
    config = paths.provider_config
    config.write_text('{"version": 1}', encoding="utf-8")
    from bookledger.db.database import Database

    CopyLifecycleService(Database(paths.database), paths.data).purge()
    assert config.read_text(encoding="utf-8") == '{"version": 1}'
