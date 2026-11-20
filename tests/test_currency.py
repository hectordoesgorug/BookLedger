from __future__ import annotations

import json
import urllib.error
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from bookledger.config_store import AppConfigStore
from bookledger.db.database import Database
from bookledger.services.backups import BackupService
from bookledger.services.currency import (
    CACHE_MAX_AGE,
    SUPPORTED_CURRENCIES,
    CurrencyService,
    ExchangeRateService,
    convert_minor,
    format_money,
)


class Backup:
    def __init__(self):
        self.calls = 0

    def create_backup(self):
        self.calls += 1
        return "recovery.zip"


def seed_money(db, *, copies=0, sales=0, srps=0, amount=12345):
    with db.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        book_ids = []
        for index in range(max(copies, srps, 1)):
            cursor = conn.execute(
                "INSERT INTO book_records(title,author,genre,srp_minor) VALUES(?,?,?,?)",
                (f"Book {index}", "Author", "Fiction", amount if index < srps else None),
            )
            book_ids.append(cursor.lastrowid)
        copy_ids = []
        for index in range(copies):
            cursor = conn.execute(
                """INSERT INTO copies(copy_uuid,book_id,copy_number,format,condition,location,photo_path,price_minor)
                   VALUES(?,?,?,?,?,?,?,?)""",
                (f"00000000-0000-4000-8000-{index:012d}", book_ids[index], 1, "Paperback", "Good", "Not Specified", f"photos/{index}.jpg", amount),
            )
            copy_ids.append(cursor.lastrowid)
        for index in range(sales):
            voided = index >= copies
            conn.execute(
                "INSERT INTO sales(copy_id,price_minor,sale_date,voided_at,void_reason) VALUES(?,?,?, ?,?)",
                (copy_ids[index % copies], amount, "2026-01-01", "2026-01-02" if voided else None, "Test" if voided else None),
            )
        conn.commit()


def mocked_rate(monkeypatch, *, rate="2", rate_date="2026-11-20", base="PHP", quote="USD"):
    calls = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self, _limit):
            return json.dumps({"date": rate_date, "base": base, "quote": quote, "rate": rate}).encode()

    def open_url(request, timeout):
        calls.append((request.full_url, timeout))
        return Response()

    monkeypatch.setattr("bookledger.services.currency.urllib.request.urlopen", open_url)
    return calls


def make_services(tmp_path, *, today=lambda: date(2026, 11, 20)):
    db = Database(tmp_path / "data" / "bookledger.sqlite3")
    config = AppConfigStore(tmp_path / "config.json")
    config.ensure_defaults({"preferences": {"currency": "PHP"}})
    backup = Backup()
    rates = ExchangeRateService(db, today=today)
    service = CurrencyService(db, rates, backup, config)
    return db, config, backup, rates, service


def test_formatting_and_decimal_conversion_cover_all_supported_currencies():
    assert len(SUPPORTED_CURRENCIES) == 20
    assert all(format_money(123456, code).endswith("1,234.56") for code in SUPPORTED_CURRENCIES)
    assert convert_minor(1, Decimal("0.5")) == 1
    assert convert_minor(3, Decimal("0.5")) == 2
    with pytest.raises(ValueError, match="zero"):
        convert_minor(1, Decimal("0.4"))
    with pytest.raises(ValueError, match="range"):
        convert_minor(2**63 - 1, Decimal("2"))


def test_empty_currency_change_is_local_and_updates_config(tmp_path, monkeypatch):
    db, config, backup, _rates, service = make_services(tmp_path)
    calls = mocked_rate(monkeypatch)
    service.set_currency("JPY", convert=False)
    assert service.current() == config.get(("preferences", "currency")) == "JPY"
    assert not calls and backup.calls == 0


def test_large_conversion_fetches_one_rate_and_converts_retained_records(tmp_path, monkeypatch):
    db, config, backup, _rates, service = make_services(tmp_path)
    seed_money(db, copies=100, sales=120, srps=2)
    calls = mocked_rate(monkeypatch)
    counts = service.set_currency("USD", convert=True)
    assert len(calls) == 1
    assert backup.calls == 1
    assert counts == {"asking_prices": 100, "sales": 120, "srps": 2}
    assert service.current() == config.get(("preferences", "currency")) == "USD"
    with db.connect() as conn:
        assert conn.execute("SELECT MIN(price_minor),MAX(price_minor) FROM copies").fetchone()[:] == (24690, 24690)
        assert conn.execute("SELECT MIN(price_minor),MAX(price_minor) FROM sales").fetchone()[:] == (24690, 24690)
        assert conn.execute("SELECT MIN(srp_minor),MAX(srp_minor) FROM book_records WHERE srp_minor IS NOT NULL").fetchone()[:] == (24690, 24690)
        audit = conn.execute("SELECT from_currency,to_currency,rate,rate_source,asking_prices,sales,srps FROM currency_conversions").fetchone()
    assert tuple(audit) == ("PHP", "USD", "2", "Frankfurter", 100, 120, 2)


def test_explicit_source_conversion_can_relabel_then_convert_saved_values(tmp_path, monkeypatch):
    db, _config, backup, _rates, service = make_services(tmp_path)
    seed_money(db, copies=1)
    calls = mocked_rate(monkeypatch, rate="2", base="USD", quote="EUR")

    service.set_currency("EUR", convert=True, source="USD")

    assert calls[0][0].endswith("/USD/EUR")
    assert backup.calls == 1
    assert service.current() == "EUR"
    with db.connect() as conn:
        assert conn.execute("SELECT price_minor FROM copies").fetchone()[0] == 24690


def test_failed_calculation_rolls_back_all_values_and_currency(tmp_path, monkeypatch):
    db, config, backup, rates, service = make_services(tmp_path)
    seed_money(db, copies=2, srps=1, amount=1)
    calls = mocked_rate(monkeypatch, rate="0.1")
    with pytest.raises(ValueError, match="zero"):
        service.set_currency("USD", convert=True, rate_info=rates.get_rate("PHP", "USD"))
    assert len(calls) == 1 and backup.calls == 1
    assert service.current() == "PHP"
    assert config.get(("preferences", "currency")) == "PHP"
    assert config.get(("currency_conversion_pending",)) is None
    with db.connect() as conn:
        assert conn.execute("SELECT price_minor FROM copies ORDER BY id").fetchall()[0][0] == 1
        assert conn.execute("SELECT COUNT(*) FROM currency_conversions").fetchone()[0] == 0


def test_same_currency_and_reconciliation_never_fetch_rates(tmp_path, monkeypatch):
    _db, config, backup, rates, service = make_services(tmp_path)
    calls = mocked_rate(monkeypatch)
    service.set_currency("PHP", convert=True)
    config.set(("preferences", "currency"), "USD")
    assert service.reconcile() == "PHP"
    assert config.get(("preferences", "currency")) == "PHP"
    assert not calls and backup.calls == 0


def test_currency_persists_after_reopening_database_and_configuration(tmp_path):
    db, config, _backup, _rates, service = make_services(tmp_path)
    service.set_currency("SGD", convert=False)
    reopened = CurrencyService(Database(db.path), ExchangeRateService(Database(db.path)), Backup(), AppConfigStore(tmp_path / "config.json"))
    assert reopened.reconcile() == "SGD"


def test_rate_failures_and_invalid_currencies_do_not_change_the_library(tmp_path, monkeypatch):
    db, _config, backup, rates, service = make_services(tmp_path)
    seed_money(db, copies=1)

    def offline(*_args, **_kwargs):
        raise urllib.error.URLError("offline")

    monkeypatch.setattr("bookledger.services.currency.urllib.request.urlopen", offline)
    with pytest.raises(RuntimeError, match="could not be reached"):
        service.set_currency("USD", convert=True)

    def timeout(*_args, **_kwargs):
        raise TimeoutError("request timed out")

    monkeypatch.setattr("bookledger.services.currency.urllib.request.urlopen", timeout)
    with pytest.raises(RuntimeError, match="could not be reached"):
        service.set_currency("USD", convert=True)
    with pytest.raises(ValueError, match="Unsupported currency"):
        rates.get_rate("PHP", "XXX")
    assert service.current() == "PHP" and backup.calls == 0


def test_invalid_pair_and_nonfinite_rates_are_rejected(tmp_path, monkeypatch):
    _db, _config, _backup, rates, _service = make_services(tmp_path)
    calls = mocked_rate(monkeypatch, rate="NaN")
    with pytest.raises(RuntimeError, match="invalid rate"):
        rates.get_rate("PHP", "USD")
    assert len(calls) == 1
    calls = mocked_rate(monkeypatch, base="EUR")
    with pytest.raises(RuntimeError, match="invalid rate"):
        rates.get_rate("PHP", "USD")
    assert len(calls) == 1


def test_cached_rate_reused_and_stale_observation_rejected(tmp_path, monkeypatch):
    db, _config, _backup, rates, _service = make_services(tmp_path)
    calls = mocked_rate(monkeypatch)
    first = rates.get_rate("PHP", "USD")
    second = rates.get_rate("PHP", "USD")
    assert first["rate"] == second["rate"] == Decimal("2")
    assert len(calls) == 1

    with db.connect() as conn:
        conn.execute(
            "UPDATE exchange_rates SET rate_date=?,retrieved_at=? WHERE base='PHP' AND quote='USD'",
            ((date(2026, 11, 20) - CACHE_MAX_AGE - timedelta(days=1)).isoformat(), datetime.now(timezone.utc).isoformat()),
        )
    calls = mocked_rate(monkeypatch, rate_date="2026-11-10")
    with pytest.raises(RuntimeError, match="stale"):
        rates.get_rate("PHP", "USD")
    assert len(calls) == 1


def test_config_write_failure_after_commit_is_reconciled_from_database(tmp_path, monkeypatch):
    _db, config, _backup, rates, service = make_services(tmp_path)
    seed_money(service.db, copies=1)
    info = rates.get_rate
    mocked_rate(monkeypatch)
    rate = info("PHP", "USD")
    original_remove = config.remove
    config.remove = lambda _path: (_ for _ in ()).throw(OSError("simulated settings interruption"))
    with pytest.raises(RuntimeError, match="committed"):
        service.set_currency("USD", convert=True, rate_info=rate)
    config.remove = original_remove
    assert service.reconcile() == "USD"
    assert config.get(("preferences", "currency")) == "USD"


def test_v12_migration_preserves_existing_numeric_values(tmp_path):
    db, _config, _backup, _rates, _service = make_services(tmp_path)
    seed_money(db, copies=1, sales=1, srps=1)
    with db.connect() as conn:
        conn.execute("DROP TABLE currency_conversions")
        conn.execute("DROP TABLE exchange_rates")
        conn.execute("DROP TABLE currency_state")
        conn.execute("ALTER TABLE book_records DROP COLUMN book_details_shortened")
        conn.execute("ALTER TABLE book_records DROP COLUMN book_details_original")
        conn.execute("PRAGMA user_version=12")
    migrated = Database(db.path)
    with migrated.connect() as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 14
        assert conn.execute("SELECT currency FROM currency_state WHERE id=1").fetchone()[0] == "PHP"
        assert conn.execute("SELECT price_minor FROM copies").fetchone()[0] == 12345
        assert conn.execute("SELECT price_minor FROM sales").fetchone()[0] == 12345
        assert conn.execute("SELECT srp_minor FROM book_records WHERE srp_minor IS NOT NULL").fetchone()[0] == 12345


def test_backup_restore_preserves_currency_cache_audit_and_configuration(tmp_path):
    db, config, _backup, _rates, service = make_services(tmp_path)
    backup_service = BackupService(db, tmp_path / "data", tmp_path / "backups", config.canonical_path)
    with db.connect() as conn:
        conn.execute("UPDATE currency_state SET currency='SGD' WHERE id=1")
        conn.execute(
            "INSERT INTO exchange_rates VALUES('PHP','SGD','0.01','2026-11-20','2026-11-20T00:00:00+00:00','Frankfurter')"
        )
        conn.execute(
            """INSERT INTO currency_conversions
               VALUES('test','PHP','SGD','0.01','2026-11-20','Frankfurter','2026-11-20T00:00:00+00:00',2,3,1)"""
        )
    config.set(("preferences", "currency"), "SGD")
    archive = backup_service.create_backup()

    with db.connect() as conn:
        conn.execute("UPDATE currency_state SET currency='PHP' WHERE id=1")
        conn.execute("DELETE FROM exchange_rates")
        conn.execute("DELETE FROM currency_conversions")
    config.set(("preferences", "currency"), "PHP")
    backup_service.restore_backup(archive)

    restored_db = Database(db.path)
    restored = CurrencyService(restored_db, ExchangeRateService(restored_db), backup_service, AppConfigStore(config.canonical_path))
    assert restored.reconcile() == "SGD"
    with restored_db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM exchange_rates").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM currency_conversions").fetchone()[0] == 1
