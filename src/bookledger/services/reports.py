from __future__ import annotations

from calendar import monthrange
from datetime import date

from bookledger.db.database import Database


class ReportService:
    """Read-only aggregate queries for inventory and sales reports."""

    def __init__(self, db: Database):
        self.db = db

    @staticmethod
    def _active_copy_predicate() -> str:
        return "NOT EXISTS (SELECT 1 FROM trash_entries t WHERE t.copy_id=c.id) AND NOT EXISTS (SELECT 1 FROM storage_operations o WHERE o.copy_id=c.id)"

    def inventory_valuation(self) -> dict[str, int]:
        with self.db.connect() as conn:
            row = conn.execute(
                f"""SELECT COALESCE(SUM(c.price_minor),0) AS total_library_value,
                           COALESCE(SUM(CASE WHEN c.status IN ('Available','Listed') THEN c.price_minor ELSE 0 END),0) AS expected_revenue
                    FROM copies c WHERE {self._active_copy_predicate()}"""
            ).fetchone()
        return {
            "total_library_value": int(row["total_library_value"]),
            "expected_revenue": int(row["expected_revenue"]),
            "sales_revenue": self.sales_revenue(),
        }

    def sales_revenue(self) -> int:
        with self.db.connect() as conn:
            value = conn.execute(
                f"""SELECT COALESCE(SUM(s.price_minor),0) FROM sales s
                    JOIN copies c ON c.id=s.copy_id WHERE {self._active_copy_predicate()}"""
            ).fetchone()[0]
        return int(value)

    def earliest_recorded_book_date(self) -> date | None:
        with self.db.connect() as conn:
            row = conn.execute(
                f"""SELECT MIN(date(b.created_at)) AS earliest_date
                    FROM book_records b JOIN copies c ON c.book_id=b.id
                    WHERE {self._active_copy_predicate()}"""
            ).fetchone()
        value = row["earliest_date"]
        try:
            return date.fromisoformat(value) if value else None
        except (TypeError, ValueError):
            return None

    def monthly_revenue(self, year: int, month: int) -> dict[int, int]:
        start = date(year, month, 1)
        end_day = monthrange(year, month)[1]
        end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
        with self.db.connect() as conn:
            rows = conn.execute(
                f"""SELECT CAST(substr(s.sale_date,9,2) AS INTEGER) AS day,
                           SUM(s.price_minor) AS revenue
                    FROM sales s JOIN copies c ON c.id=s.copy_id
                    WHERE s.sale_date >= ? AND s.sale_date < ?
                      AND {self._active_copy_predicate()}
                    GROUP BY s.sale_date ORDER BY s.sale_date""",
                (start.isoformat(), end.isoformat()),
            ).fetchall()
        return {int(row["day"]): int(row["revenue"]) for row in rows if 1 <= int(row["day"]) <= end_day}

    def books_by_genre(self) -> list[dict[str, int | str]]:
        with self.db.connect() as conn:
            rows = conn.execute(
                f"""SELECT b.genre,COUNT(*) AS copy_count FROM copies c
                    JOIN book_records b ON b.id=c.book_id
                    WHERE {self._active_copy_predicate()}
                    GROUP BY b.genre ORDER BY copy_count DESC,b.genre COLLATE NOCASE"""
            ).fetchall()
        return [{"genre": str(row["genre"]), "copy_count": int(row["copy_count"])} for row in rows]
