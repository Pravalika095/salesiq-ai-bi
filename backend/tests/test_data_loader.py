"""CSV import pipeline tests."""

from __future__ import annotations

import csv
import sqlite3
from decimal import Decimal

import pytest

from app.data_loader import CSVValidationError, import_csv
from app.database import read_connection
from app import analytics

from .conftest import REAL_CSV


def _rows(db_path, sql, params=()):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def test_import_valid_records(csv_path, db_path):
    summary = import_csv(csv_path, db_path)
    assert summary["total_rows"] == 11
    assert summary["imported_rows"] == 7
    assert summary["rejected_rows"] == 4
    assert summary["duplicate_rows"] == 1
    assert _rows(db_path, "SELECT order_date FROM sales_transactions WHERE transaction_id='T1'") == [("2026-01-05",)]


def test_duplicate_transaction_ids_keep_first_occurrence(csv_path, db_path):
    import_csv(csv_path, db_path)
    assert _rows(db_path, "SELECT order_date, quantity FROM sales_transactions WHERE transaction_id='T2'") == [
        ("2026-01-10", 1)
    ]
    reasons = _rows(db_path, "SELECT reason FROM rejected_rows WHERE transaction_id='T2'")
    assert len(reasons) == 1 and "duplicate" in reasons[0][0]


def test_missing_unit_price_is_null_flagged_and_excluded(csv_path, db_path):
    import_csv(csv_path, db_path)
    row = _rows(db_path, "SELECT unit_price_paise, quality_flags FROM sales_transactions WHERE transaction_id='T6'")
    assert row == [(None, "missing_unit_price")]  # stored as NULL, not 0
    assert _rows(db_path, "SELECT COUNT(*) FROM eligible_sales WHERE transaction_id='T6'") == [(0,)]


def test_invalid_rows_rejected_with_reasons(csv_path, db_path):
    import_csv(csv_path, db_path)
    reasons = dict(_rows(db_path, "SELECT transaction_id, reason FROM rejected_rows WHERE transaction_id <> 'T2'"))
    assert "invalid order_date" in reasons["T8"]
    assert "negative quantity" in reasons["T9"]
    assert "non-numeric unit_price" in reasons["T10"]


def test_import_is_idempotent(csv_path, db_path):
    import_csv(csv_path, db_path)
    second = import_csv(csv_path, db_path)
    assert second["skipped"] is True
    assert _rows(db_path, "SELECT COUNT(*) FROM sales_transactions") == [(7,)]
    forced = import_csv(csv_path, db_path, force=True)
    assert forced["skipped"] is False
    assert _rows(db_path, "SELECT COUNT(*) FROM sales_transactions") == [(7,)]


def test_missing_required_column_is_rejected(tmp_path, db_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("Transaction_Id,Order_date,Product\nT1,01-01-2026,A\n", encoding="utf-8")
    with pytest.raises(CSVValidationError):
        import_csv(bad, db_path)


def test_real_dataset_total_matches_independent_calculation(tmp_path):
    """Recompute the supplied CSV's revenue with plain csv + Decimal and compare."""
    expected = Decimal(0)
    count = 0
    with REAL_CSV.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row["Status"].strip() != "Completed" or not row["Unit_price"].strip():
                continue
            expected += Decimal(row["Quantity"]) * Decimal(row["Unit_price"]) - Decimal(row["Discount_amount"])
            count += 1

    db = tmp_path / "real.db"
    import_csv(REAL_CSV, db)
    with read_connection(db) as conn:
        total = analytics.total_revenue(conn)
    assert Decimal(str(total["revenue"])) == expected
    assert total["transactions"] == count
