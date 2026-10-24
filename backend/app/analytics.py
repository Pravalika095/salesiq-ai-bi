"""Approved analytical operations.

Every function here runs a fixed, parameterized SELECT against the
``eligible_sales`` view (the single definition of revenue). Nothing in this
module accepts SQL text from the outside. The only dynamic SQL fragment is a
GROUP BY column, and that is looked up from the ``DIMENSIONS`` allowlist,
never taken from user input directly.

Amounts are summed as integer paise in SQLite and converted to rupees
(rounded to 2 decimals) only when returned.
"""

from __future__ import annotations

import re
import sqlite3
from typing import Any

from .database import fetch_all, fetch_one

# Public dimension name -> column name. The allowlist for GROUP BY.
DIMENSIONS: dict[str, str] = {
    "product": "product",
    "region": "region",
    "category": "category",
    "channel": "sales_channel",
}

MONTH_PATTERN = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")


class InvalidParameterError(ValueError):
    """A user-supplied parameter failed validation (safe to show to users)."""


def to_rupees(paise: int | None) -> float:
    return round((paise or 0) / 100, 2)


def validate_month(value: str) -> str:
    if not isinstance(value, str) or not MONTH_PATTERN.match(value.strip()):
        raise InvalidParameterError(f"'{value}' is not a valid month; use YYYY-MM (e.g. 2026-01).")
    return value.strip()


def _month_clause(month: str | None) -> tuple[str, tuple]:
    if month is None:
        return "", ()
    return " WHERE order_month = ?", (validate_month(month),)


# --------------------------------------------------------------------------- #
# Basic facts about the dataset
# --------------------------------------------------------------------------- #

def available_months(conn: sqlite3.Connection) -> list[str]:
    rows = fetch_all(conn, "SELECT DISTINCT order_month FROM sales_transactions ORDER BY order_month")
    return [r["order_month"] for r in rows]


def date_range(conn: sqlite3.Connection) -> dict[str, str | None]:
    row = fetch_one(conn, "SELECT MIN(order_date) AS start, MAX(order_date) AS end FROM sales_transactions")
    return {"start": row["start"] if row else None, "end": row["end"] if row else None}


# --------------------------------------------------------------------------- #
# A. Total revenue (+ total units)
# --------------------------------------------------------------------------- #

def total_revenue(conn: sqlite3.Connection, month: str | None = None) -> dict[str, Any]:
    where, params = _month_clause(month)
    row = fetch_one(
        conn,
        "SELECT COALESCE(SUM(net_revenue_paise), 0) AS net,"
        "       COALESCE(SUM(gross_revenue_paise), 0) AS gross,"
        "       COALESCE(SUM(discount_paise), 0) AS discounts,"
        "       COUNT(*) AS transactions,"
        "       COALESCE(SUM(quantity), 0) AS units"
        f" FROM eligible_sales{where}",
        params,
    )
    return {
        "revenue": to_rupees(row["net"]),
        "gross_revenue": to_rupees(row["gross"]),
        "discounts": to_rupees(row["discounts"]),
        "transactions": row["transactions"],
        "units": row["units"],
        "month": month,
    }


# --------------------------------------------------------------------------- #
# B/D. Revenue grouped by a dimension; top / bottom performer
# --------------------------------------------------------------------------- #

def revenue_by(conn: sqlite3.Connection, dimension: str, month: str | None = None) -> list[dict[str, Any]]:
    """Revenue per product/region/category/channel, highest first.

    Ties are broken alphabetically by name so results are deterministic.
    """
    column = DIMENSIONS.get(dimension)
    if column is None:
        raise InvalidParameterError(f"Unsupported dimension '{dimension}'.")
    where, params = _month_clause(month)
    rows = fetch_all(
        conn,
        f"SELECT {column} AS label,"
        "        SUM(net_revenue_paise) AS net,"
        "        COUNT(*) AS transactions,"
        "        SUM(quantity) AS units"
        f" FROM eligible_sales{where}"
        f" GROUP BY {column}"
        f" ORDER BY net DESC, {column} ASC",
        params,
    )
    total = sum(r["net"] for r in rows)
    return [
        {
            "label": r["label"],
            "revenue": to_rupees(r["net"]),
            "transactions": r["transactions"],
            "units": r["units"],
            "share_pct": round(r["net"] * 100 / total, 2) if total else 0.0,
        }
        for r in rows
    ]


def ranked(conn: sqlite3.Connection, dimension: str, month: str | None = None,
           lowest: bool = False) -> dict[str, Any]:
    """Highest (or lowest) revenue item in a dimension, reporting ties."""
    rows = revenue_by(conn, dimension, month)
    if not rows:
        return {"winner": None, "tied": [], "rows": []}
    target = rows[-1]["revenue"] if lowest else rows[0]["revenue"]
    tied = sorted(r["label"] for r in rows if r["revenue"] == target)
    winner = next(r for r in rows if r["label"] == tied[0])
    return {"winner": winner, "tied": tied, "rows": rows}


# --------------------------------------------------------------------------- #
# C. Monthly trend
# --------------------------------------------------------------------------- #

def _month_sequence(first: str, last: str) -> list[str]:
    year, month = map(int, first.split("-"))
    end_year, end_month = map(int, last.split("-"))
    out = []
    while (year, month) <= (end_year, end_month):
        out.append(f"{year:04d}-{month:02d}")
        month += 1
        if month > 12:
            year, month = year + 1, 1
    return out


def pct_change(previous_paise: int, current_paise: int) -> float | None:
    """Percentage change; None when the previous value is zero (undefined)."""
    if previous_paise == 0:
        return None
    return round((current_paise - previous_paise) * 100 / previous_paise, 2)


def monthly_revenue(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Revenue per calendar month (YYYY-MM), chronological, gaps filled with 0."""
    months = available_months(conn)
    if not months:
        return []
    rows = fetch_all(
        conn,
        "SELECT order_month AS month, SUM(net_revenue_paise) AS net,"
        "       COUNT(*) AS transactions, SUM(quantity) AS units"
        " FROM eligible_sales GROUP BY order_month ORDER BY order_month",
    )
    by_month = {r["month"]: r for r in rows}
    result = []
    previous: int | None = None
    for month in _month_sequence(months[0], months[-1]):
        r = by_month.get(month, {"net": 0, "transactions": 0, "units": 0})
        net = r["net"] or 0
        result.append({
            "month": month,
            "revenue": to_rupees(net),
            "transactions": r["transactions"],
            "units": r["units"] or 0,
            "change": None if previous is None else to_rupees(net - previous),
            "change_pct": None if previous is None else pct_change(previous, net),
        })
        previous = net
    return result


# --------------------------------------------------------------------------- #
# E. Month comparison
# --------------------------------------------------------------------------- #

def _month_net(conn: sqlite3.Connection, month: str) -> tuple[int, int]:
    row = fetch_one(
        conn,
        "SELECT COALESCE(SUM(net_revenue_paise), 0) AS net, COUNT(*) AS n"
        " FROM eligible_sales WHERE order_month = ?",
        (month,),
    )
    return row["net"], row["n"]


def compare_months(conn: sqlite3.Connection, first_month: str, second_month: str) -> dict[str, Any]:
    """Change from ``first_month`` (previous) to ``second_month`` (current).

    absolute change = second - first
    percentage change = (second - first) / first * 100, or None if first == 0
    """
    first_month = validate_month(first_month)
    second_month = validate_month(second_month)
    if first_month == second_month:
        raise InvalidParameterError("Please choose two different months to compare.")

    months = available_months(conn)
    missing = [m for m in (first_month, second_month) if m not in months]
    if missing:
        span = f"{months[0]} to {months[-1]}" if months else "none"
        raise InvalidParameterError(
            f"No sales data for {', '.join(missing)}. Available months: {span}."
        )

    first_net, first_n = _month_net(conn, first_month)
    second_net, second_n = _month_net(conn, second_month)
    diff = second_net - first_net
    direction = "increased" if diff > 0 else "decreased" if diff < 0 else "unchanged"
    return {
        "first_month": first_month,
        "second_month": second_month,
        "first_revenue": to_rupees(first_net),
        "second_revenue": to_rupees(second_net),
        "first_transactions": first_n,
        "second_transactions": second_n,
        "absolute_change": to_rupees(diff),
        "percent_change": pct_change(first_net, second_net),
        "direction": direction,
    }


# --------------------------------------------------------------------------- #
# Data quality and transaction listing
# --------------------------------------------------------------------------- #

def data_quality(conn: sqlite3.Connection) -> dict[str, Any]:
    run = fetch_one(conn, "SELECT * FROM import_runs ORDER BY id DESC LIMIT 1")
    counts = fetch_one(
        conn,
        "SELECT COUNT(*) AS stored,"
        " SUM(status = 'Returned') AS returned,"
        " SUM(unit_price_paise IS NULL) AS missing_unit_price,"
        " SUM(quantity = 0) AS zero_quantity,"
        " SUM(instr(quality_flags, 'unknown_status') > 0) AS unknown_status,"
        " SUM(instr(quality_flags, 'discount_exceeds_gross') > 0) AS discount_exceeds_gross"
        " FROM sales_transactions",
    )
    eligible = fetch_one(conn, "SELECT COUNT(*) AS n FROM eligible_sales")
    flagged = fetch_all(
        conn,
        "SELECT transaction_id, order_date, product, status, quantity,"
        "       unit_price_paise, quality_flags,"
        "       transaction_id IN (SELECT transaction_id FROM eligible_sales) AS counted"
        " FROM sales_transactions WHERE quality_flags <> '' ORDER BY source_row",
    )
    rejected = fetch_all(
        conn,
        "SELECT source_row, transaction_id, reason FROM rejected_rows ORDER BY source_row",
    )
    return {
        "import": {
            "source_file": run["source_file"] if run else None,
            "imported_at": run["imported_at"] if run else None,
            "total_rows": run["total_rows"] if run else 0,
            "imported_rows": run["imported_rows"] if run else 0,
            "rejected_rows": run["rejected_rows"] if run else 0,
            "duplicate_rows": run["duplicate_rows"] if run else 0,
        },
        "eligible_transactions": eligible["n"],
        "excluded_from_revenue": (counts["stored"] or 0) - eligible["n"],
        "issues": {
            "returned": counts["returned"] or 0,
            "missing_unit_price": counts["missing_unit_price"] or 0,
            "zero_quantity": counts["zero_quantity"] or 0,
            "unknown_status": counts["unknown_status"] or 0,
            "discount_exceeds_gross": counts["discount_exceeds_gross"] or 0,
        },
        "flagged_records": [
            {
                "transaction_id": r["transaction_id"],
                "order_date": r["order_date"],
                "product": r["product"],
                "status": r["status"],
                "quantity": r["quantity"],
                "unit_price": None if r["unit_price_paise"] is None else to_rupees(r["unit_price_paise"]),
                "flags": r["quality_flags"].split(","),
                "counted_in_revenue": bool(r["counted"]),
            }
            for r in flagged
        ],
        "rejected_records": rejected,
    }


TRANSACTION_FILTERS = {"product": "product", "region": "region", "status": "status",
                       "category": "category", "channel": "sales_channel"}


def list_transactions(conn: sqlite3.Connection, page: int, page_size: int,
                      filters: dict[str, str | None]) -> dict[str, Any]:
    clauses, params = [], []
    for key, value in filters.items():
        column = TRANSACTION_FILTERS.get(key)
        if column and value:
            clauses.append(f"t.{column} = ?")
            params.append(value)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""

    total = fetch_one(conn, f"SELECT COUNT(*) AS n FROM sales_transactions t{where}", tuple(params))["n"]
    rows = fetch_all(
        conn,
        "SELECT t.*, e.net_revenue_paise FROM sales_transactions t"
        " LEFT JOIN eligible_sales e ON e.transaction_id = t.transaction_id"
        f"{where} ORDER BY t.order_date, t.transaction_id LIMIT ? OFFSET ?",
        (*params, page_size, (page - 1) * page_size),
    )
    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "items": [
            {
                "transaction_id": r["transaction_id"],
                "order_date": r["order_date"],
                "product": r["product"],
                "category": r["category"],
                "region": r["region"],
                "sales_channel": r["sales_channel"],
                "quantity": r["quantity"],
                "unit_price": None if r["unit_price_paise"] is None else to_rupees(r["unit_price_paise"]),
                "discount": to_rupees(r["discount_paise"]),
                "status": r["status"],
                "net_revenue": None if r["net_revenue_paise"] is None else to_rupees(r["net_revenue_paise"]),
                "flags": [f for f in r["quality_flags"].split(",") if f],
            }
            for r in rows
        ],
    }


def filter_options(conn: sqlite3.Connection) -> dict[str, list[str]]:
    return {
        key: [r["v"] for r in fetch_all(conn, f"SELECT DISTINCT {col} AS v FROM sales_transactions ORDER BY v")]
        for key, col in TRANSACTION_FILTERS.items()
    }
