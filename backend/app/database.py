"""SQLite schema, connections and the read-only query path.

Two kinds of connection exist:

* ``write_connection`` — used only by the CSV import pipeline (controlled
  write path, wrapped in a transaction).
* ``read_connection`` — used by every analytics query. It is opened with
  ``mode=ro``, has ``PRAGMA query_only=ON`` and installs an SQLite authorizer
  that denies everything except SELECT/READ/FUNCTION actions. Even if some
  code path tried to run ``DROP TABLE`` here, SQLite itself would refuse.

Money is stored as INTEGER paise (1/100 of a rupee) so sums are exact.
"""

from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

logger = logging.getLogger("salesiq.database")


class DatabaseError(Exception):
    """Raised for database failures; message is safe to log, not to show users."""


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sales_transactions (
    transaction_id   TEXT PRIMARY KEY,
    order_date       TEXT NOT NULL,              -- ISO 8601 (YYYY-MM-DD)
    order_month      TEXT NOT NULL,              -- YYYY-MM, for grouping
    product          TEXT NOT NULL,
    category         TEXT NOT NULL,
    region           TEXT NOT NULL,
    sales_channel    TEXT NOT NULL,
    quantity         INTEGER NOT NULL CHECK (quantity >= 0),
    unit_price_paise INTEGER CHECK (unit_price_paise IS NULL OR unit_price_paise >= 0),
    discount_paise   INTEGER NOT NULL CHECK (discount_paise >= 0),
    status           TEXT NOT NULL,
    quality_flags    TEXT NOT NULL DEFAULT '',   -- comma-separated review flags
    source_row       INTEGER NOT NULL            -- 1-based data row in the CSV
);

CREATE INDEX IF NOT EXISTS idx_sales_order_month ON sales_transactions(order_month);
CREATE INDEX IF NOT EXISTS idx_sales_product     ON sales_transactions(product);
CREATE INDEX IF NOT EXISTS idx_sales_region      ON sales_transactions(region);
CREATE INDEX IF NOT EXISTS idx_sales_status      ON sales_transactions(status);

-- The ONE place the revenue rule lives. Every analytic reads from this view.
-- Net revenue = quantity * unit price - discount, for Completed sales with a
-- known unit price and a discount that does not exceed the gross amount.
CREATE VIEW IF NOT EXISTS eligible_sales AS
SELECT
    t.*,
    t.quantity * t.unit_price_paise                    AS gross_revenue_paise,
    t.quantity * t.unit_price_paise - t.discount_paise AS net_revenue_paise
FROM sales_transactions AS t
WHERE t.status = 'Completed'
  AND t.unit_price_paise IS NOT NULL
  AND t.quantity * t.unit_price_paise >= t.discount_paise;

CREATE TABLE IF NOT EXISTS rejected_rows (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    source_row     INTEGER NOT NULL,
    transaction_id TEXT,
    reason         TEXT NOT NULL,
    raw_json       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS import_runs (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file    TEXT NOT NULL,
    source_sha256  TEXT NOT NULL,
    imported_at    TEXT NOT NULL,
    total_rows     INTEGER NOT NULL,
    imported_rows  INTEGER NOT NULL,
    rejected_rows  INTEGER NOT NULL,
    duplicate_rows INTEGER NOT NULL
);
"""

# Authorizer action codes that a read-only analytics query legitimately needs.
_ALLOWED_READ_ACTIONS = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION}
_RECURSIVE = getattr(sqlite3, "SQLITE_RECURSIVE", None)
if _RECURSIVE is not None:
    _ALLOWED_READ_ACTIONS.add(_RECURSIVE)


def _read_only_authorizer(action: int, *_args: Any) -> int:
    return sqlite3.SQLITE_OK if action in _ALLOWED_READ_ACTIONS else sqlite3.SQLITE_DENY


def initialize_schema(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with write_connection(db_path) as conn:
        conn.executescript(SCHEMA_SQL)


@contextmanager
def write_connection(db_path: Path) -> Iterator[sqlite3.Connection]:
    """Connection for the controlled write path (schema + CSV import).

    Commits on success, rolls back on any exception.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def read_connection(db_path: Path) -> Iterator[sqlite3.Connection]:
    """Read-only connection used by all analytics queries."""
    if not db_path.exists():
        raise DatabaseError("Database file does not exist")
    try:
        conn = sqlite3.connect(f"{db_path.resolve().as_uri()}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        raise DatabaseError(f"Could not open database read-only: {exc}") from exc
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA query_only = ON")
        conn.set_authorizer(_read_only_authorizer)
        yield conn
    finally:
        conn.close()


def fetch_all(conn: sqlite3.Connection, sql: str, params: tuple | dict = ()) -> list[dict[str, Any]]:
    """Run one parameterized SELECT and return rows as dicts."""
    try:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]
    except sqlite3.Error as exc:
        logger.exception("Query failed")
        raise DatabaseError(str(exc)) from exc


def fetch_one(conn: sqlite3.Connection, sql: str, params: tuple | dict = ()) -> dict[str, Any] | None:
    rows = fetch_all(conn, sql, params)
    return rows[0] if rows else None


def check_connection(db_path: Path) -> tuple[bool, bool]:
    """Return (database reachable, sales data loaded)."""
    try:
        with read_connection(db_path) as conn:
            row = fetch_one(conn, "SELECT COUNT(*) AS n FROM sales_transactions")
            return True, bool(row and row["n"] > 0)
    except DatabaseError:
        return False, False
