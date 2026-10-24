"""Analytics calculations against the controlled fixture (see conftest for expected values)."""

from __future__ import annotations

import sqlite3

import pytest

from app import analytics
from app.analytics import InvalidParameterError
from app.data_loader import import_csv
from app.database import read_connection


def test_total_revenue(loaded_db):
    with read_connection(loaded_db) as conn:
        result = analytics.total_revenue(conn)
    assert result["revenue"] == 1150.0
    assert result["gross_revenue"] == 1200.0
    assert result["discounts"] == 50.0
    assert result["transactions"] == 5
    assert result["units"] == 10


def test_total_revenue_for_one_month(loaded_db):
    with read_connection(loaded_db) as conn:
        assert analytics.total_revenue(conn, "2026-02")["revenue"] == 500.0


def test_top_product(loaded_db):
    with read_connection(loaded_db) as conn:
        result = analytics.ranked(conn, "product")
    assert result["winner"]["label"] == "A"
    assert result["winner"]["revenue"] == 500.0
    assert [r["label"] for r in result["rows"]] == ["A", "B", "C"]


def test_bottom_product(loaded_db):
    with read_connection(loaded_db) as conn:
        assert analytics.ranked(conn, "product", lowest=True)["winner"]["label"] == "C"


def test_top_region(loaded_db):
    with read_connection(loaded_db) as conn:
        result = analytics.ranked(conn, "region")
    assert result["winner"]["label"] == "South"
    assert result["winner"]["revenue"] == 750.0


def test_monthly_grouping_is_chronological(loaded_db):
    with read_connection(loaded_db) as conn:
        rows = analytics.monthly_revenue(conn)
    assert [(r["month"], r["revenue"]) for r in rows] == [
        ("2026-01", 650.0), ("2026-02", 500.0), ("2026-03", 0.0)
    ]
    assert rows[0]["change"] is None
    assert rows[1]["change"] == -150.0
    assert rows[2]["change_pct"] == -100.0


def test_compare_months_absolute_and_percentage_change(loaded_db):
    with read_connection(loaded_db) as conn:
        result = analytics.compare_months(conn, "2026-01", "2026-02")
    assert result["absolute_change"] == -150.0
    assert result["percent_change"] == pytest.approx(-23.08)
    assert result["direction"] == "decreased"


def test_compare_months_zero_previous_revenue_does_not_divide_by_zero(loaded_db):
    with read_connection(loaded_db) as conn:
        result = analytics.compare_months(conn, "2026-03", "2026-01")
    assert result["first_revenue"] == 0.0
    assert result["absolute_change"] == 650.0
    assert result["percent_change"] is None
    assert result["direction"] == "increased"


@pytest.mark.parametrize("first,second", [
    ("2026-13", "2026-01"),
    ("January", "2026-02"),
    ("2026-01'; DROP TABLE sales_transactions;--", "2026-02"),
    ("2026-01", "2026-01"),
    ("2025-12", "2026-01"),  # valid format but no data
])
def test_invalid_month_parameters_rejected(loaded_db, first, second):
    with read_connection(loaded_db) as conn:
        with pytest.raises(InvalidParameterError):
            analytics.compare_months(conn, first, second)


def test_ties_are_broken_alphabetically(tmp_path):
    csv_file = tmp_path / "tie.csv"
    csv_file.write_text(
        "Transaction_Id,Order_date,Product,Category,Region,Sales_channel,Quantity,Unit_price,Discount_amount,Status\n"
        "X1,01-01-2026,Zeta,C,North,Online,1,100,0,Completed\n"
        "X2,01-01-2026,Alpha,C,South,Online,1,100,0,Completed\n",
        encoding="utf-8",
    )
    db = tmp_path / "tie.db"
    import_csv(csv_file, db)
    with read_connection(db) as conn:
        result = analytics.ranked(conn, "product")
    assert result["winner"]["label"] == "Alpha"
    assert result["tied"] == ["Alpha", "Zeta"]


def test_read_connection_refuses_writes(loaded_db):
    with read_connection(loaded_db) as conn:
        for statement in ("DROP TABLE sales_transactions",
                          "DELETE FROM sales_transactions",
                          "UPDATE sales_transactions SET quantity = 999",
                          "INSERT INTO rejected_rows (source_row, reason, raw_json) VALUES (1, 'x', '{}')",
                          "ATTACH DATABASE 'evil.db' AS evil"):
            with pytest.raises(sqlite3.Error):
                conn.execute(statement)
    conn = sqlite3.connect(loaded_db)
    assert conn.execute("SELECT COUNT(*), SUM(quantity) FROM sales_transactions").fetchone() == (7, 16)
    conn.close()
