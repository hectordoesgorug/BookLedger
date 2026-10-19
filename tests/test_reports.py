from datetime import date
from types import MethodType, SimpleNamespace

from bookledger.app import BookLedgerApp
from bookledger.db.database import Database
from bookledger.services.reports import ReportService


def _report_db(tmp_path):
    db = Database(tmp_path / "bookledger.sqlite3")
    with db.connect() as conn:
        books = [
            ("A title", "A", "2026-10-10T00:00:00.000Z"),
            ("B title", "B", "2026-10-02T00:00:00.000Z"),
            ("No copy", "Empty", "2020-01-01T00:00:00.000Z"),
        ]
        book_ids = []
        for title, genre, created in books:
            cursor = conn.execute(
                "INSERT INTO book_records(title,author,genre,created_at) VALUES(?,?,?,?)",
                (title, "Author", genre, created),
            )
            book_ids.append(cursor.lastrowid)
        copies = [
            (book_ids[0], 1, 10000, "Available"),
            (book_ids[0], 2, 20000, "Listed"),
            (book_ids[0], 3, 30000, "Sold"),
            (book_ids[1], 1, 40000, "Not for Sale"),
        ]
        copy_ids = []
        for index, (book_id, number, price, status) in enumerate(copies, 1):
            cursor = conn.execute(
                """INSERT INTO copies(copy_code,book_id,copy_number,format,condition,photo_path,price_minor,status)
                   VALUES(?,?,?,'Paperback','Good','photos/test.jpg',?,?)""",
                (f"BL-{index:06d}", book_id, number, price, status),
            )
            copy_ids.append(cursor.lastrowid)
        conn.execute("INSERT INTO sales(copy_id,price_minor,sale_date) VALUES(?,?,?)", (copy_ids[2], 12500, "2026-10-04"))
        conn.execute("INSERT INTO sales(copy_id,price_minor,sale_date) VALUES(?,?,?)", (copy_ids[2], 7500, "2026-10-04"))
        conn.execute("INSERT INTO sales(copy_id,price_minor,sale_date) VALUES(?,?,?)", (copy_ids[2], 9000, "2026-11-01"))
    return db


def test_inventory_valuation_uses_physical_copy_prices_and_actual_sale_prices(tmp_path):
    reports = ReportService(_report_db(tmp_path))

    assert reports.inventory_valuation() == {
        "total_library_value": 100000,
        "expected_revenue": 30000,
        "sales_revenue": 29000,
    }


def test_monthly_revenue_groups_actual_sales_by_sale_date_and_month(tmp_path):
    reports = ReportService(_report_db(tmp_path))

    assert reports.monthly_revenue(2026, 10) == {4: 20000}
    assert reports.monthly_revenue(2026, 11) == {1: 9000}
    assert reports.monthly_revenue(2026, 9) == {}


def test_earliest_recorded_date_ignores_books_without_active_copies(tmp_path):
    reports = ReportService(_report_db(tmp_path))

    assert reports.earliest_recorded_book_date() == date(2026, 10, 2)
    assert reports.earliest_recorded_book_date().replace(day=1) == date(2026, 10, 1)


def test_books_by_genre_counts_physical_copies_in_descending_order(tmp_path):
    reports = ReportService(_report_db(tmp_path))

    assert reports.books_by_genre() == [
        {"genre": "A", "copy_count": 3},
        {"genre": "B", "copy_count": 1},
    ]


def test_empty_inventory_and_sales_have_clean_report_data(tmp_path):
    reports = ReportService(Database(tmp_path / "empty.sqlite3"))

    assert reports.earliest_recorded_book_date() is None
    assert reports.inventory_valuation() == {
        "total_library_value": 0,
        "expected_revenue": 0,
        "sales_revenue": 0,
    }
    assert reports.monthly_revenue(2026, 10) == {}
    assert reports.books_by_genre() == []


class _SortTree:
    def __init__(self):
        self.rows = {}
        self.order = []
        self.headings = {}

    def get_children(self):
        return tuple(self.order)

    def insert(self, _parent, index, *, iid, values):
        self.rows[iid] = values
        if index == "end":
            self.order.append(iid)
        else:
            self.order.insert(index, iid)

    def move(self, iid, _parent, index):
        self.order.remove(iid)
        self.order.insert(index, iid)

    def set_children(self, _parent, *items):
        self.order = list(items)

    def heading(self, column, *, text, command=None):
        self.headings[column] = (text, command)


def test_sale_history_sort_cycles_descending_ascending_then_copy_id_default():
    rows = [
        {"sale_id": 10, "copy_id": 9, "copy_code": "BL-000009", "title": "Alpha", "author": "A", "sale_date": "2026-01-01", "price_minor": 100},
        {"sale_id": 11, "copy_id": 2, "copy_code": "BL-000002", "title": "Zulu", "author": "Z", "sale_date": "2026-02-01", "price_minor": 300},
        {"sale_id": 12, "copy_id": 5, "copy_code": "BL-000005", "title": "Beta", "author": "B", "sale_date": "2026-03-01", "price_minor": 200},
    ]
    tree = _SortTree()
    subject = SimpleNamespace(
        _sales_rows=rows,
        _sales_sort_column=None,
        _sales_sort_state=0,
        tree=tree,
        money=lambda value: str(value),
        _sales_sort_key=BookLedgerApp._sales_sort_key,
        _default_sales_order=BookLedgerApp._default_sales_order,
    )
    subject._render_sales_rows = MethodType(BookLedgerApp._render_sales_rows, subject)

    BookLedgerApp._render_sales_rows(subject, rows)
    BookLedgerApp._sort_sales(subject, "title")
    assert tree.order == ["11", "12", "10"]  # Descending
    assert tree.headings["title"][0] == "Title ↓"
    BookLedgerApp._sort_sales(subject, "title")
    assert tree.order == ["10", "12", "11"]  # Ascending
    assert tree.headings["title"][0] == "Title ↑"
    BookLedgerApp._sort_sales(subject, "title")
    assert tree.order == ["11", "12", "10"]  # Copy ID ascending: 2, 5, 9
    assert tree.headings["title"][0] == "Title"
    assert subject._sales_rows == rows


def test_sale_history_double_click_never_opens_edit_book():
    tree = SimpleNamespace(winfo_exists=lambda: True, identify_row=lambda _y: "10", selection=lambda: ("10",))
    opened = []
    subject = SimpleNamespace(tree=tree, current_page="Sale History", open_selected_edit=opened.append)

    assert BookLedgerApp._on_tree_double_click(subject, SimpleNamespace(widget=tree, y=1)) == "break"
    assert opened == []


def test_month_navigation_helper_crosses_year_boundary():
    assert BookLedgerApp._month_shift(date(2026, 1, 1), -1) == date(2025, 12, 1)
    assert BookLedgerApp._month_shift(date(2025, 12, 1), 1) == date(2026, 1, 1)


def test_month_navigation_stops_at_earliest_date_and_without_a_start_date():
    updates = []
    subject = SimpleNamespace(
        _report_month=date(2026, 10, 1),
        _report_earliest_month=date(2026, 10, 1),
        _report_today=date(2026, 10, 1),
        _month_shift=BookLedgerApp._month_shift,
        _update_monthly_revenue=lambda: updates.append("updated"),
    )
    BookLedgerApp._move_report_month(subject, -1)
    assert subject._report_month == date(2026, 10, 1)
    assert updates == []

    subject._report_earliest_month = None
    BookLedgerApp._move_report_month(subject, -1)
    assert subject._report_month == date(2026, 10, 1)
    assert updates == []


def test_empty_month_clears_chart_axes_and_shows_empty_state():
    class Control:
        def __init__(self):
            self.options = {}
            self.packed = False

        def configure(self, **options):
            self.options.update(options)

        def pack(self, **_options):
            self.packed = True

        def pack_forget(self):
            self.packed = False

        def delete(self, *args):
            self.deleted = args

    canvas, empty, label, previous, next_button = (Control() for _ in range(5))
    subject = SimpleNamespace(
        _report_month=date(2026, 10, 1),
        _report_earliest_month=date(2026, 10, 1),
        _report_today=date(2026, 10, 1),
        _report_month_label=label,
        _report_prev=previous,
        _report_next=next_button,
        _revenue_canvas=canvas,
        _revenue_empty=empty,
        reports=SimpleNamespace(monthly_revenue=lambda _year, _month: {}),
        _draw_monthly_revenue=lambda: (_ for _ in ()).throw(AssertionError("empty chart must not draw axes")),
    )

    BookLedgerApp._update_monthly_revenue(subject)

    assert label.options["text"] == "October 2026"
    assert previous.options["state"] == "disabled"
    assert next_button.options["state"] == "disabled"
    assert canvas.deleted == ("all",)
    assert not canvas.packed
    assert empty.packed
