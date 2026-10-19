from datetime import date
from types import MethodType, SimpleNamespace

from bookledger import app as app_module
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
            (book_ids[0], 4, 40000, "Sold"),
            (book_ids[0], 5, 50000, "Sold"),
            (book_ids[1], 1, 60000, "Not for Sale"),
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
        conn.execute("INSERT INTO sales(copy_id,price_minor,sale_date) VALUES(?,?,?)", (copy_ids[3], 7500, "2026-10-04"))
        conn.execute("INSERT INTO sales(copy_id,price_minor,sale_date) VALUES(?,?,?)", (copy_ids[4], 9000, "2026-11-01"))
        conn.execute("INSERT INTO sales(copy_id,price_minor,sale_date,voided_at) VALUES(?,?,?,?)", (copy_ids[2], 50000, "2026-10-04", "2026-10-05T00:00:00Z"))
    return db


def test_inventory_valuation_uses_physical_copy_prices_and_actual_sale_prices(tmp_path):
    reports = ReportService(_report_db(tmp_path))

    assert reports.inventory_valuation() == {
        "total_library_value": 210000,
        "expected_revenue": 30000,
        "sales_revenue": 29000,
    }


def test_monthly_revenue_groups_actual_sales_by_sale_date_and_month(tmp_path):
    reports = ReportService(_report_db(tmp_path))

    assert reports.monthly_revenue(2026, 10) == {4: 20000}
    assert reports.monthly_revenue(2026, 11) == {1: 9000}
    assert reports.monthly_revenue(2026, 9) == {}


def test_voided_sales_remain_in_history_data_but_do_not_count_as_revenue(tmp_path):
    db = _report_db(tmp_path)
    from bookledger.services.catalog import CatalogService

    history = CatalogService(db).list_sales()
    assert any(row["voided_at"] and row["price_minor"] == 50000 for row in history)
    assert ReportService(db).sales_revenue() == 29000


def test_earliest_recorded_date_ignores_books_without_active_copies(tmp_path):
    reports = ReportService(_report_db(tmp_path))

    assert reports.earliest_recorded_book_date() == date(2026, 10, 2)
    assert reports.earliest_recorded_book_date().replace(day=1) == date(2026, 10, 1)


def test_books_by_genre_counts_physical_copies_in_descending_order(tmp_path):
    reports = ReportService(_report_db(tmp_path))

    assert reports.books_by_genre() == [
        {"genre": "A", "copy_count": 5},
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

    def insert(self, _parent, index, *, iid, values, tags=()):
        self.rows[iid] = values
        self.item_tags = getattr(self, "item_tags", {})
        self.item_tags[iid] = tags
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

    def tag_configure(self, tag, **options):
        self.tags = getattr(self, "tags", {})
        self.tags[tag] = options


def test_voided_sale_rows_use_gray_overstrike_tag_and_preserve_history_values():
    rows = [
        {"sale_id": 1, "copy_id": 7, "copy_code": "BL-000007", "title": "History", "author": "Writer", "sale_date": "2026-01-02", "price_minor": 12345, "voided_at": "2026-01-03T00:00:00Z"},
    ]
    tree = _SortTree()
    subject = SimpleNamespace(tree=tree, money=lambda value: f"PHP {value}")
    BookLedgerApp._configure_sale_history_tree_styles(subject)
    subject._render_sales_rows = MethodType(BookLedgerApp._render_sales_rows, subject)
    subject._render_sales_rows(rows)

    assert tree.tags["voided_sale"]["foreground"] == "#858585"
    assert "overstrike" in tree.tags["voided_sale"]["font"]
    assert tree.rows["1"] == ("BL-000007", "History", "Writer", "2026-01-02", "PHP 12345")
    assert tree.item_tags["1"] == ("voided_sale",)


def test_sale_history_build_configures_voided_row_styles_and_keeps_columns(monkeypatch):
    labels = []

    class Widget:
        def pack(self, **_options):
            pass

    class Tree(_SortTree):
        columns = ("code", "title", "author", "sale_date", "sale_price")

        def __getitem__(self, key):
            assert key == "columns"
            return self.columns

    tree = Tree()
    monkeypatch.setattr(app_module.ttk, "Frame", lambda _parent: Widget())
    monkeypatch.setattr(app_module.ttk, "Label", lambda _parent, **options: labels.append(options) or Widget())
    subject = SimpleNamespace(
        workspace=object(),
        catalog=SimpleNamespace(list_sales=lambda: []),
        reports=SimpleNamespace(sales_revenue=lambda: 12345),
        tree=None,
        status_var=SimpleNamespace(set=lambda _message: None),
        money=lambda value: f"PHP {value}",
        _make_tree=lambda *_args, **_kwargs: setattr(subject, "tree", tree),
        _default_sales_order=BookLedgerApp._default_sales_order,
        _render_sales_rows=lambda _rows: None,
        _configure_sale_history_tree_styles=MethodType(BookLedgerApp._configure_sale_history_tree_styles, SimpleNamespace(tree=tree)),
        after_idle=lambda _callback: None,
        _refresh_sale_strikethroughs=lambda: None,
    )

    BookLedgerApp._build_sales(subject)

    assert tree.columns == ("code", "title", "author", "sale_date", "sale_price")
    assert tree.tags["voided_sale"]["foreground"] == "#858585"
    assert labels[0]["text"] == "Sale History · Revenue PHP 12345"


def test_voided_sale_draws_red_strikethrough_overlay_and_leaves_active_row_normal(monkeypatch):
    class Canvas:
        def __init__(self, _parent, **options):
            self.options = options
            self.lines = []
            self.bindings = []
            captured.append(self)

        def create_line(self, *args, **options):
            self.lines.append((args, options))

        def place(self, **options):
            self.placement = options

        def bind(self, sequence, _callback):
            self.bindings.append(sequence)

        def winfo_exists(self):
            return True

        def destroy(self):
            self.destroyed = True

    class Tree:
        def winfo_exists(self):
            return True

        def bbox(self, item):
            return (3, 20, 400, 30) if item == "1" else ()

    captured = []
    monkeypatch.setattr(app_module.tk, "Canvas", Canvas)
    monkeypatch.setattr(app_module.ttk, "Style", lambda _parent: SimpleNamespace(lookup=lambda *_args: "#ffffff"))
    subject = SimpleNamespace(
        current_page="Sale History",
        tree=Tree(),
        tree_container=SimpleNamespace(winfo_exists=lambda: True),
        _sales_strike_overlays=[],
        _sales_rows=[
            {"sale_id": 1, "voided_at": "2026-01-03T00:00:00Z"},
            {"sale_id": 2, "voided_at": None},
        ],
    )

    BookLedgerApp._refresh_sale_strikethroughs(subject)

    assert len(captured) == 1
    assert captured[0].lines == [((0, 1, 400, 1), {"fill": "#c62828", "width": 1})]
    assert captured[0].placement == {"x": 3, "y": 35, "width": 400, "height": 2}
    assert "<Button-1>" in captured[0].bindings
    assert "<MouseWheel>" in captured[0].bindings


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
