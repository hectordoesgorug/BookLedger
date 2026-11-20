from __future__ import annotations

import json
import sqlite3
import urllib.error
import urllib.request
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

SUPPORTED_CURRENCIES = {
    "PHP": "₱", "USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥",
    "AUD": "A$", "CAD": "CA$", "SGD": "S$", "CNY": "CN¥", "HKD": "HK$",
    "KRW": "₩", "INR": "₹", "TWD": "NT$", "THB": "฿", "MYR": "RM",
    "IDR": "Rp", "NZD": "NZ$", "CHF": "Fr", "AED": "د.إ", "SAR": "﷼",
}
MAX_MINOR = 2**63 - 1
RATE_SOURCE = "Frankfurter"
CACHE_MAX_AGE = timedelta(days=5)


def validate_currency(currency: str) -> str:
    code = str(currency).upper()
    if code not in SUPPORTED_CURRENCIES:
        raise ValueError(f"Unsupported currency: {currency}")
    return code


def format_money(minor: int | None, currency: str) -> str:
    code = validate_currency(currency)
    amount = Decimal(int(minor or 0)) / 100
    return f"{code} {SUPPORTED_CURRENCIES[code]}{amount:,.2f}"


def convert_minor(minor: int, rate: Decimal) -> int:
    try:
        converted = (Decimal(int(minor)) * rate).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, OverflowError) as exc:
        raise ValueError("The converted amount is outside the supported monetary range.") from exc
    result = int(converted)
    if result <= 0 or result > MAX_MINOR:
        raise ValueError("The converted amount rounds to zero or exceeds the supported monetary range.")
    return result


class ExchangeRateService:
    """Validated Frankfurter rates, cached only when an authorized caller requests them."""

    def __init__(self, db, *, timeout: float = 5.0, today=date.today):
        self.db = db
        self.timeout = timeout
        self.today = today

    def get_rate(self, base: str, quote: str) -> dict:
        base, quote = validate_currency(base), validate_currency(quote)
        if base == quote:
            return {"base": base, "quote": quote, "rate": Decimal("1"), "rate_date": self.today().isoformat(), "source": "Identity"}
        now = datetime.now(timezone.utc)
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT rate,rate_date,retrieved_at,source FROM exchange_rates WHERE base=? AND quote=? ORDER BY rate_date DESC",
                (base, quote),
            ).fetchall()
        stale_date = None
        for row in rows:
            rate_date = date.fromisoformat(row["rate_date"])
            retrieved = datetime.fromisoformat(row["retrieved_at"])
            if rate_date <= self.today() and self.today() - rate_date <= CACHE_MAX_AGE and timedelta(0) <= now - retrieved <= CACHE_MAX_AGE:
                return {"base": base, "quote": quote, "rate": self._rate(row["rate"]), "rate_date": rate_date.isoformat(), "source": row["source"]}
            if stale_date is None:
                stale_date = rate_date

        request = urllib.request.Request(
            f"https://api.frankfurter.dev/v2/rate/{base}/{quote}",
            headers={"Accept": "application/json", "User-Agent": "BookLedger/1.2"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read(64 * 1024 + 1)
        except urllib.error.HTTPError as exc:
            reason = f"A cached rate dated {stale_date} is stale. " if stale_date else ""
            raise RuntimeError(f"{reason}Frankfurter returned HTTP {exc.code}.") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            reason = f"The cached {base}/{quote} rate dated {stale_date} is stale. " if stale_date else ""
            raise RuntimeError(f"{reason}Frankfurter could not be reached. Check the connection and try again.") from exc
        if len(raw) > 64 * 1024:
            raise RuntimeError("Frankfurter returned an unexpectedly large response.")
        try:
            payload = json.loads(raw)
            rate_date = date.fromisoformat(payload["date"])
            if payload["base"].upper() != base or payload["quote"].upper() != quote:
                raise ValueError("currency pair did not match the request")
            rate = self._rate(payload["rate"])
        except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            raise RuntimeError("Frankfurter returned an invalid rate response.") from exc
        if rate_date > self.today():
            raise RuntimeError("Frankfurter returned a future observation date.")
        if self.today() - rate_date > CACHE_MAX_AGE:
            raise RuntimeError(f"Frankfurter's latest {base}/{quote} rate is stale ({rate_date.isoformat()}); conversion was not applied.")
        result = {"base": base, "quote": quote, "rate": rate, "rate_date": rate_date.isoformat(), "source": RATE_SOURCE}
        with self.db.connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO exchange_rates(base,quote,rate,rate_date,retrieved_at,source) VALUES(?,?,?,?,?,?)",
                (base, quote, str(rate), rate_date.isoformat(), now.isoformat(), RATE_SOURCE),
            )
        return result

    @staticmethod
    def _rate(value) -> Decimal:
        try:
            rate = Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("invalid exchange rate") from exc
        if not rate.is_finite() or rate <= 0:
            raise ValueError("invalid exchange rate")
        return rate


class CurrencyService:
    """Owns application currency and transactional conversion of every retained amount."""

    def __init__(self, db, exchange_rates: ExchangeRateService, backup, config_store):
        self.db = db
        self.exchange_rates = exchange_rates
        self.backup = backup
        self.config_store = config_store
        self.warning = ""

    def current(self) -> str:
        with self.db.connect() as conn:
            row = conn.execute("SELECT currency FROM currency_state WHERE id=1").fetchone()
        return validate_currency(row[0])

    def monetary_counts(self, *, source: str | None = None) -> dict[str, int]:
        source = validate_currency(source or self.current())
        with self.db.connect() as conn:
            return self._counts(conn, source)

    @staticmethod
    def _counts(conn, source: str) -> dict[str, int]:
        copies = conn.execute("SELECT COUNT(*) FROM copies").fetchone()[0]
        sales = conn.execute("SELECT COUNT(*) FROM sales").fetchone()[0]
        srps = conn.execute("SELECT COUNT(*) FROM book_records WHERE srp_minor IS NOT NULL").fetchone()[0]
        return {"asking_prices": int(copies), "sales": int(sales), "srps": int(srps)}

    def set_currency(self, destination: str, *, convert: bool, rate_info: dict | None = None, source: str | None = None) -> dict[str, int]:
        destination = validate_currency(destination)
        current = self.current()
        source = validate_currency(source or current)
        if destination == current and not convert:
            return {"asking_prices": 0, "sales": 0, "srps": 0}
        if destination == source:
            return {"asking_prices": 0, "sales": 0, "srps": 0}
        with self.db.operation_guard():
            with self.db.connect() as conn:
                counts = self._counts(conn, source)
            if convert and any(counts.values()):
                if rate_info is None:
                    rate_info = self.exchange_rates.get_rate(source, destination)
                if rate_info["base"] != source or rate_info["quote"] != destination:
                    raise ValueError("The exchange rate does not match this conversion.")
                recovery = self.backup.create_backup()
                operation_id = str(uuid.uuid4())
                journal = {"id": operation_id, "from": source, "to": destination}
                self.config_store.set(("currency_conversion_pending",), journal)
                try:
                    self._convert_database(operation_id, current, source, destination, rate_info, counts)
                except Exception:
                    self._clear_pending()
                    raise
                try:
                    self._finish_configuration(destination)
                except Exception as exc:
                    raise RuntimeError(
                        f"The conversion committed with recovery backup {recovery}, but settings need repair on next launch: {exc}"
                    ) from exc
                return counts
            # Store the database value first; startup reconciles a failed config write.
            with self.db.connect() as conn:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute("UPDATE currency_state SET currency=? WHERE id=1", (destination,))
                conn.commit()
            self._finish_configuration(destination)
            return {"asking_prices": 0, "sales": 0, "srps": 0}

    def _convert_database(self, operation_id, expected_currency, source, destination, rate_info, counts):
        rate = ExchangeRateService._rate(rate_info["rate"])
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            state = conn.execute("SELECT currency FROM currency_state WHERE id=1").fetchone()[0]
            if state != expected_currency:
                raise RuntimeError("The library currency changed during conversion; no values were changed.")
            for table, key in (("copies", "id"), ("sales", "id"), ("book_records", "id")):
                column = "price_minor" if table in ("copies", "sales") else "srp_minor"
                predicate = "" if table != "book_records" else " WHERE srp_minor IS NOT NULL"
                rows = conn.execute(f"SELECT {key},{column} FROM {table}{predicate}").fetchall()
                for row in rows:
                    converted = convert_minor(row[column], rate)
                    conn.execute(f"UPDATE {table} SET {column}=? WHERE {key}=?", (converted, row[key]))
            conn.execute("UPDATE currency_state SET currency=? WHERE id=1", (destination,))
            conn.execute(
                """INSERT INTO currency_conversions(id,from_currency,to_currency,rate,rate_date,rate_source,operation_at,asking_prices,sales,srps)
                   VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (operation_id, source, destination, str(rate), rate_info["rate_date"], rate_info["source"], datetime.now(timezone.utc).isoformat(), counts["asking_prices"], counts["sales"], counts["srps"]),
            )
            conn.commit()

    def _finish_configuration(self, currency):
        self.config_store.set(("preferences", "currency"), currency)
        self.config_store.remove(("currency_conversion_pending",))

    def _clear_pending(self):
        try:
            self.config_store.remove(("currency_conversion_pending",))
        except Exception:
            pass

    def reconcile(self):
        """Database state is authoritative after interruption; mirror it in config."""
        self.warning = ""
        currency = self.current()
        if self.config_store.get(("preferences", "currency"), "PHP") != currency or self.config_store.get(("currency_conversion_pending",)):
            try:
                self._finish_configuration(currency)
            except Exception as exc:
                self.warning = f"Currency settings need reconciliation: {exc}"
        return currency
