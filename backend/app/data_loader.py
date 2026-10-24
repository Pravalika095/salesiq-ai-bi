"""CSV -> SQLite import pipeline.

Steps: read CSV with pandas (all columns as text) -> normalise headers ->
validate required columns -> parse dates/numbers explicitly -> validate each
row -> deduplicate transaction IDs -> insert valid rows and record rejected
rows with reasons, all inside ONE transaction.

Idempotency: the SHA-256 of the CSV is stored in ``import_runs``. If the same
file has already been imported, the import is skipped. ``force=True`` (or
``python -m app.data_loader --reload``) wipes and re-imports atomically.

Row policy (see README "Data-cleaning policy"):
  * Rejected (not stored in sales_transactions): missing ID/date/text fields,
    unparseable or impossible dates, missing/non-numeric/negative/fractional
    quantity, non-numeric or negative unit price or discount, missing discount,
    and repeated transaction IDs (the first occurrence wins).
  * Stored but flagged for review: missing unit price (kept as NULL, never
    turned into 0, excluded from revenue), zero quantity, returned status,
    unknown status, discount larger than the gross amount.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import pandas as pd

from .database import initialize_schema, write_connection

logger = logging.getLogger("salesiq.loader")

REQUIRED_COLUMNS = [
    "transaction_id",
    "order_date",
    "product",
    "category",
    "region",
    "sales_channel",
    "quantity",
    "unit_price",
    "discount_amount",
    "status",
]
TEXT_FIELDS = ["product", "category", "region", "sales_channel"]
DATE_FORMAT = "%d-%m-%Y"  # The supplied file uses DD-MM-YYYY, e.g. 03-01-2026.
KNOWN_STATUSES = {"Completed", "Returned", "Cancelled", "Pending"}


class CSVValidationError(Exception):
    """The CSV as a whole cannot be imported (missing file or columns)."""


def normalize_header(name: str) -> str:
    return "_".join(str(name).strip().lower().replace("-", " ").split())


def _to_paise(value: str) -> int:
    """'1200' -> 120000. Raises ValueError for non-numeric input."""
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(value) from exc
    if not amount.is_finite():
        raise ValueError(value)
    return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _parse_row(raw: dict[str, str]) -> tuple[dict[str, Any] | None, str | None]:
    """Validate one CSV row. Returns (clean_row, None) or (None, reason)."""
    txn_id = raw["transaction_id"].strip()
    if not txn_id:
        return None, "missing transaction_id"

    date_text = raw["order_date"].strip()
    if not date_text:
        return None, "missing order_date"
    try:
        order_date = datetime.strptime(date_text, DATE_FORMAT).date()
    except ValueError:
        return None, f"invalid order_date '{date_text}' (expected DD-MM-YYYY)"

    texts = {}
    for field in TEXT_FIELDS:
        value = raw[field].strip()
        if not value:
            return None, f"missing {field}"
        texts[field] = value

    qty_text = raw["quantity"].strip()
    if not qty_text:
        return None, "missing quantity"
    try:
        qty_dec = Decimal(qty_text)
    except InvalidOperation:
        return None, f"non-numeric quantity '{qty_text}'"
    if not qty_dec.is_finite() or qty_dec != qty_dec.to_integral_value():
        return None, f"quantity must be a whole number, got '{qty_text}'"
    quantity = int(qty_dec)
    if quantity < 0:
        return None, f"negative quantity {quantity}"

    flags: list[str] = []

    price_text = raw["unit_price"].strip()
    unit_price_paise: int | None
    if not price_text:
        unit_price_paise = None  # Kept as NULL: unknown, not zero.
        flags.append("missing_unit_price")
    else:
        try:
            unit_price_paise = _to_paise(price_text)
        except ValueError:
            return None, f"non-numeric unit_price '{price_text}'"
        if unit_price_paise < 0:
            return None, f"negative unit_price {price_text}"

    discount_text = raw["discount_amount"].strip()
    if not discount_text:
        return None, "missing discount_amount"
    try:
        discount_paise = _to_paise(discount_text)
    except ValueError:
        return None, f"non-numeric discount_amount '{discount_text}'"
    if discount_paise < 0:
        return None, f"negative discount_amount {discount_text}"

    status_text = raw["status"].strip()
    if not status_text:
        return None, "missing status"
    status = status_text.title()
    if status == "Returned":
        flags.append("returned")
    elif status not in KNOWN_STATUSES:
        flags.append("unknown_status")

    if quantity == 0:
        flags.append("zero_quantity")
    if unit_price_paise is not None and discount_paise > quantity * unit_price_paise:
        flags.append("discount_exceeds_gross")

    return {
        "transaction_id": txn_id,
        "order_date": order_date.isoformat(),
        "order_month": order_date.strftime("%Y-%m"),
        **texts,
        "quantity": quantity,
        "unit_price_paise": unit_price_paise,
        "discount_paise": discount_paise,
        "status": status,
        "quality_flags": ",".join(flags),
    }, None


def read_csv(csv_path: Path) -> pd.DataFrame:
    if not csv_path.exists():
        raise CSVValidationError(f"CSV file not found: {csv_path.name}")
    # Read everything as text so nothing is silently coerced (e.g. blank -> NaN -> 0).
    df = pd.read_csv(csv_path, dtype=str, keep_default_na=False, skip_blank_lines=True)
    df.columns = [normalize_header(c) for c in df.columns]
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise CSVValidationError(f"CSV is missing required columns: {', '.join(missing)}")
    return df[REQUIRED_COLUMNS]


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def import_csv(csv_path: Path, db_path: Path, force: bool = False) -> dict[str, Any]:
    """Import the CSV into SQLite. Returns an import summary dict."""
    initialize_schema(db_path)
    digest = _file_sha256(csv_path) if csv_path.exists() else ""

    with write_connection(db_path) as conn:
        last = conn.execute(
            "SELECT * FROM import_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        loaded = conn.execute("SELECT COUNT(*) FROM sales_transactions").fetchone()[0]
        if not force and last is not None and last["source_sha256"] == digest and loaded > 0:
            logger.info("CSV unchanged since last import; skipping (idempotent).")
            return {**dict(last), "skipped": True}

    df = read_csv(csv_path)

    valid: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    first_seen: dict[str, int] = {}
    duplicates = 0

    for index, raw in enumerate(df.to_dict(orient="records"), start=1):
        row, reason = _parse_row(raw)
        txn_id = raw["transaction_id"].strip() or None
        if row is not None and row["transaction_id"] in first_seen:
            duplicates += 1
            row, reason = None, (
                f"duplicate transaction_id (first seen at data row {first_seen[txn_id]})"
            )
        if row is None:
            rejected.append({
                "source_row": index,
                "transaction_id": txn_id,
                "reason": reason,
                "raw_json": json.dumps(raw, ensure_ascii=False),
            })
            continue
        first_seen[row["transaction_id"]] = index
        row["source_row"] = index
        valid.append(row)

    summary = {
        "source_file": csv_path.name,
        "source_sha256": digest,
        "imported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "total_rows": len(df),
        "imported_rows": len(valid),
        "rejected_rows": len(rejected),
        "duplicate_rows": duplicates,
    }

    # Single transaction: either the whole dataset is replaced or nothing changes.
    with write_connection(db_path) as conn:
        conn.execute("DELETE FROM sales_transactions")
        conn.execute("DELETE FROM rejected_rows")
        conn.executemany(
            """INSERT INTO sales_transactions (
                   transaction_id, order_date, order_month, product, category, region,
                   sales_channel, quantity, unit_price_paise, discount_paise, status,
                   quality_flags, source_row)
               VALUES (:transaction_id, :order_date, :order_month, :product, :category,
                   :region, :sales_channel, :quantity, :unit_price_paise, :discount_paise,
                   :status, :quality_flags, :source_row)""",
            valid,
        )
        conn.executemany(
            """INSERT INTO rejected_rows (source_row, transaction_id, reason, raw_json)
               VALUES (:source_row, :transaction_id, :reason, :raw_json)""",
            rejected,
        )
        conn.execute(
            """INSERT INTO import_runs (source_file, source_sha256, imported_at, total_rows,
                   imported_rows, rejected_rows, duplicate_rows)
               VALUES (:source_file, :source_sha256, :imported_at, :total_rows,
                   :imported_rows, :rejected_rows, :duplicate_rows)""",
            summary,
        )

    logger.info(
        "Imported %s rows (%s rejected, %s duplicates) from %s",
        summary["imported_rows"], summary["rejected_rows"], duplicates, csv_path.name,
    )
    return {**summary, "skipped": False}


def main() -> None:
    from .config import load_settings

    parser = argparse.ArgumentParser(description="Import the sales CSV into SQLite.")
    parser.add_argument("--reload", action="store_true", help="Wipe and re-import even if unchanged.")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = load_settings()
    summary = import_csv(settings.csv_path, settings.db_path, force=args.reload)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
