from __future__ import annotations

import json

import pytest

from bookledger.config_store import AppConfigStore
from bookledger.db.database import Database
from bookledger.provider_settings import ProviderSettings, ProviderSettingsStore
from bookledger.services.catalog import CatalogService, ValidationError


def _assigned_data(db: Database) -> None:
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO book_records(id,title,author,genre) VALUES(1,'Book','Writer','Science')"
        )
        conn.execute(
            "INSERT INTO copies(id,copy_code,book_id,copy_number,format,condition,location,photo_path,price_minor) "
            "VALUES(1,'BL-000001',1,1,'Paperback','Good','Shelf','photos/1.jpg',10000)"
        )
        conn.execute(
            "INSERT INTO app_meta(key,value) VALUES('genre_options',?)",
            (json.dumps(['Science', 'Legacy Genre']),),
        )
        conn.execute(
            "INSERT INTO app_meta(key,value) VALUES('format_options',?)",
            (json.dumps(['Paperback', 'Legacy Format']),),
        )
        conn.execute("INSERT OR IGNORE INTO locations(name) VALUES('Shelf')")
        conn.execute("INSERT OR IGNORE INTO locations(name) VALUES('Unassigned Shelf')")
        conn.execute(
            "INSERT INTO app_meta(key,value) VALUES('diagnostic_logging_enabled','1')"
        )


def test_migration_imports_google_key_lists_logging_and_preserves_other_config(tmp_path):
    db = Database(tmp_path / 'data' / 'bookledger.sqlite3')
    _assigned_data(db)
    canonical = tmp_path / 'config.json'
    canonical.write_text(
        json.dumps({'version': 3, 'metadata_providers': {'enabled': ['booktopia']}, 'custom': {'keep': True}}),
        encoding='utf-8',
    )
    legacy = tmp_path / 'data' / 'assets' / 'google_books.json'
    legacy.parent.mkdir(parents=True)
    legacy.write_text(json.dumps({'api_key': 'synthetic-key'}), encoding='utf-8')
    store = AppConfigStore(canonical)

    warnings = store.migrate_legacy_settings(db, legacy)

    document = json.loads(canonical.read_text(encoding='utf-8'))
    assert document['version'] == 3
    assert document['metadata_providers'] == {'enabled': ['booktopia']}
    assert document['custom'] == {'keep': True}
    assert document['api_keys']['google_books'] == 'synthetic-key'
    assert document['preferences']['genres'] == ['Science', 'Legacy Genre']
    assert document['preferences']['formats'] == ['Paperback', 'Legacy Format']
    assert document['preferences']['locations'] == ['Not Specified', 'Shelf', 'Unassigned Shelf']
    assert document['logging']['enabled'] is True
    assert document['migration_state']['configuration_v1'] is True
    assert document['migration_state']['google_books_legacy_checked'] is True
    assert not legacy.exists()
    assert all('synthetic-key' not in warning for warning in warnings)

    # A later migration must not rewrite newer canonical values from stale SQLite.
    store.set(('preferences', 'genres'), ['Custom Newest'])
    warnings = store.migrate_legacy_settings(db, legacy)
    assert store.get(('preferences', 'genres')) == ['Custom Newest', 'Science']
    assert not legacy.exists()


def test_canonical_precedence_intentionally_empty_lists_and_removal_marker(tmp_path):
    db = Database(tmp_path / 'bookledger.sqlite3')
    canonical = tmp_path / 'config.json'
    canonical.write_text(json.dumps({
        'api_keys': {'google_books': 'canonical-key'},
        'preferences': {'genres': [], 'formats': [], 'locations': []},
        'logging': {'enabled': False},
        'unrelated': {'retain': 1},
    }), encoding='utf-8')
    legacy = tmp_path / 'google_books.json'
    legacy.write_text(json.dumps({'api_key': 'legacy-key'}), encoding='utf-8')
    store = AppConfigStore(canonical)

    warnings = store.migrate_legacy_settings(db, legacy)

    assert store.get(('api_keys', 'google_books')) == 'canonical-key'
    assert store.get(('preferences', 'genres')) == []
    assert store.get(('preferences', 'formats')) == []
    assert store.get(('preferences', 'locations')) == []
    assert store.get(('logging', 'enabled')) is False
    assert store.get(('unrelated', 'retain')) == 1
    assert legacy.is_file()
    assert any('took precedence' in warning for warning in warnings)

    store.remove(('api_keys', 'google_books'))
    store.migrate_legacy_settings(db, legacy)
    assert store.get(('api_keys', 'google_books')) is None
    assert legacy.is_file()


def test_missing_and_malformed_legacy_files_are_safe_and_retryable(tmp_path):
    db = Database(tmp_path / 'bookledger.sqlite3')
    canonical = tmp_path / 'config.json'
    store = AppConfigStore(canonical)
    warnings = store.migrate_legacy_settings(db, tmp_path / 'missing.json')
    assert canonical.is_file()
    assert store.get(('api_keys', 'google_books')) == ''
    assert not warnings

    store = AppConfigStore(tmp_path / 'retry.json')
    malformed = tmp_path / 'malformed.json'
    malformed.write_text('{broken', encoding='utf-8')
    warnings = store.migrate_legacy_settings(db, malformed)
    assert malformed.is_file()
    assert any('could not be read' in warning for warning in warnings)
    assert store.get(('migration_state', 'google_books_legacy_checked')) is None


def test_legacy_google_books_extra_fields_are_preserved_in_inactive_file(tmp_path):
    db = Database(tmp_path / 'bookledger.sqlite3')
    canonical = tmp_path / 'config.json'
    legacy = tmp_path / 'google_books.json'
    legacy.write_text(json.dumps({'api_key': 'synthetic-key', 'region': 'US'}), encoding='utf-8')
    store = AppConfigStore(canonical)

    warnings = store.migrate_legacy_settings(db, legacy)

    assert store.get(('api_keys', 'google_books')) == 'synthetic-key'
    assert json.loads(legacy.read_text(encoding='utf-8'))['region'] == 'US'
    assert store.get(('migration_state', 'google_books_legacy_checked')) is True
    assert any('Unrecognized Google Books settings' in warning for warning in warnings)


def test_malformed_canonical_config_is_preserved_and_writes_are_blocked(tmp_path):
    canonical = tmp_path / 'config.json'
    canonical.write_text('{invalid json', encoding='utf-8')
    store = AppConfigStore(canonical)

    with pytest.raises(ValueError, match='preserved'):
        store.set(('api_keys', 'google_books'), 'synthetic-key')

    assert canonical.read_text(encoding='utf-8') == '{invalid json'


def test_malformed_root_and_fallback_files_are_both_preserved(tmp_path):
    canonical = tmp_path / 'config.json'
    fallback = tmp_path / 'profile-config.json'
    canonical.write_text('{root broken', encoding='utf-8')
    fallback.write_text('{fallback broken', encoding='utf-8')
    store = AppConfigStore(canonical, fallback)

    with pytest.raises(ValueError, match='preserved'):
        store.set(('preferences', 'genres'), ['Fiction'])

    assert canonical.read_text(encoding='utf-8') == '{root broken'
    assert fallback.read_text(encoding='utf-8') == '{fallback broken'


def test_canonical_values_win_while_missing_values_can_be_recovered_from_fallback(tmp_path):
    canonical = tmp_path / 'config.json'
    fallback = tmp_path / 'profile-config.json'
    canonical.write_text(json.dumps({'preferences': {'genres': ['Canonical']}}), encoding='utf-8')
    fallback.write_text(json.dumps({
        'preferences': {'genres': ['Stale'], 'formats': ['Paperback']},
        'custom': {'recover': True},
    }), encoding='utf-8')
    store = AppConfigStore(canonical, fallback)

    assert store.get(('preferences', 'genres')) == ['Canonical']
    assert store.get(('preferences', 'formats')) == ['Paperback']
    assert store.get(('custom', 'recover')) is True
    assert store.active_path == canonical


def test_failed_migration_write_preserves_existing_config_and_legacy_key(tmp_path, monkeypatch):
    db = Database(tmp_path / 'bookledger.sqlite3')
    canonical = tmp_path / 'config.json'
    original = json.dumps({'metadata_providers': {'order': ['open_library']}})
    canonical.write_text(original, encoding='utf-8')
    legacy = tmp_path / 'google_books.json'
    legacy.write_text(json.dumps({'api_key': 'synthetic-key'}), encoding='utf-8')
    store = AppConfigStore(canonical)

    def fail_write(_path, _document):
        raise OSError('simulated write failure')

    monkeypatch.setattr(AppConfigStore, '_atomic_write', staticmethod(fail_write))
    warnings = store.migrate_legacy_settings(db, legacy)

    assert canonical.read_text(encoding='utf-8') == original
    assert legacy.is_file()
    assert any('incomplete' in warning for warning in warnings)


def test_config_backed_catalog_renames_assignments_and_keeps_app_meta_legacy(tmp_path):
    db = Database(tmp_path / 'bookledger.sqlite3')
    _assigned_data(db)
    store = AppConfigStore(tmp_path / 'config.json')
    store.set(('preferences', 'genres'), ['Science', 'Legacy Genre'])
    store.set(('preferences', 'formats'), ['Paperback', 'Legacy Format'])
    store.set(('preferences', 'locations'), ['Not Specified', 'Shelf', 'Unassigned Shelf'])
    catalog = CatalogService(db, tmp_path / 'data', config_store=store)

    catalog.rename_genre('Science', 'Natural Science')
    catalog.rename_format('Paperback', 'Softcover')
    catalog.rename_location('Shelf', 'Bookcase')

    with db.connect() as conn:
        assert conn.execute('SELECT genre FROM book_records WHERE id=1').fetchone()[0] == 'Natural Science'
        row = conn.execute('SELECT format,location FROM copies WHERE id=1').fetchone()
        assert tuple(row) == ('Softcover', 'Bookcase')
        assert conn.execute("SELECT value FROM app_meta WHERE key='genre_options'").fetchone()[0] == '["Science", "Legacy Genre"]'
    assert catalog.list_genres() == ('Natural Science', 'Legacy Genre')
    assert catalog.list_formats() == ('Softcover', 'Legacy Format')
    assert catalog.list_locations() == ('Not Specified', 'Bookcase', 'Unassigned Shelf')
    assert catalog.value_assignment_count('genre', 'Natural Science') == 1
    assert catalog.value_assignment_count('format', 'Softcover') == 1
    assert catalog.location_assignment_count('Bookcase') == 1
    with pytest.raises(ValidationError):
        catalog.delete_genre('Natural Science')
    with pytest.raises(ValidationError):
        catalog.delete_format('Softcover')
    with pytest.raises(ValidationError):
        catalog.delete_location('Bookcase')

    catalog.add_genre('New Genre')
    catalog.add_format('New Format')
    catalog.add_location('New Shelf')
    catalog.delete_genre('New Genre')
    catalog.delete_format('New Format')
    catalog.delete_location('New Shelf')
    assert 'New Genre' not in catalog.list_genres()
    assert 'New Format' not in catalog.list_formats()
    assert 'New Shelf' not in catalog.list_locations()


def test_shared_provider_settings_update_only_provider_section(tmp_path):
    canonical = tmp_path / 'config.json'
    canonical.write_text(json.dumps({
        'api_keys': {'google_books': 'synthetic-key'},
        'preferences': {'genres': ['Fiction']},
        'custom': {'keep': True},
    }), encoding='utf-8')
    config_store = AppConfigStore(canonical)
    settings_store = ProviderSettingsStore(canonical, tmp_path / 'fallback.json', config_store=config_store)

    settings_store.save(ProviderSettings.defaults())

    document = json.loads(canonical.read_text(encoding='utf-8'))
    assert document['api_keys']['google_books'] == 'synthetic-key'
    assert document['preferences']['genres'] == ['Fiction']
    assert document['custom'] == {'keep': True}
    assert document['metadata_providers'] == ProviderSettings.defaults().to_document()['metadata_providers']
