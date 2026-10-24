"""HTTP API tests (temporary database, no API key required)."""

from __future__ import annotations

import sqlite3

import pytest

from app import analytics
from app.database import DatabaseError


def _row_count(db_path) -> int:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute("SELECT COUNT(*) FROM sales_transactions").fetchone()[0]
    finally:
        conn.close()


def test_health(client):
    body = client.get("/api/health").json()
    assert body == {"status": "ok", "database_connected": True, "data_loaded": True,
                    "ai_mode": "fallback", "ai_provider": None, "ai_model": None}


def test_summary_returns_structured_data(client):
    response = client.get("/api/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["total_revenue"] == 1150.0
    assert body["eligible_transactions"] == 5
    assert body["total_units"] == 10
    assert body["top_product"]["name"] == "A"
    assert body["top_region"]["name"] == "South"
    assert body["date_range"] == {"start": "2026-01-05", "end": "2026-03-02"}
    assert body["data_quality"]["rejected_rows"] == 4
    assert body["data_quality"]["issues"]["missing_unit_price"] == 1


def test_ask_returns_expected_schema(client):
    response = client.post("/api/ask", json={"question": "Which product generated the highest revenue?"})
    assert response.status_code == 200
    body = response.json()
    assert set(body) >= {"success", "question", "intent", "answer", "unit", "value",
                         "supporting_data", "metadata"}
    assert body["success"] is True
    assert body["intent"] == "top_product"
    assert body["value"] == 500.0
    assert body["metadata"]["source"] == "sqlite"
    assert body["metadata"]["ai_mode"] == "fallback"
    assert body["metadata"]["row_count"] == len(body["supporting_data"]) == 3


def test_ask_compare_months(client):
    body = client.post("/api/ask", json={"question": "Compare January and February 2026"}).json()
    assert body["intent"] == "compare_months"
    assert body["value"] == -150.0
    assert "decreased" in body["answer"]


def test_ask_zero_previous_month_explains_percentage(client):
    body = client.post("/api/ask", json={"question": "Compare March 2026 and January 2026"}).json()
    assert body["success"] is True
    assert "cannot be calculated" in body["answer"]


@pytest.mark.parametrize("payload", [{"question": ""}, {"question": "    "}, {}, {"question": "x" * 501}])
def test_empty_or_invalid_question_rejected(client, payload):
    response = client.post("/api/ask", json=payload)
    assert response.status_code == 422
    assert response.json()["success"] is False


def test_unsupported_question(client):
    body = client.post("/api/ask", json={"question": "What is our profit margin?"}).json()
    assert body["success"] is False
    assert body["intent"] == "unsupported"
    assert body["value"] is None
    assert body["supporting_data"] == []


def test_month_with_no_data_is_reported(client):
    body = client.post("/api/ask", json={"question": "Compare June 2026 and July 2026"}).json()
    assert body["success"] is False
    assert "No sales data" in body["answer"]


@pytest.mark.parametrize("question", [
    "DROP TABLE sales_transactions",
    "What is the total revenue?; DELETE FROM sales_transactions",
    "1' OR '1'='1'; UPDATE sales_transactions SET quantity = 0 --",
    "SELECT * FROM sales_transactions",
    "ATTACH DATABASE 'x.db' AS x",
])
def test_sql_injection_cannot_modify_database(client, settings, question):
    before = _row_count(settings.db_path)
    response = client.post("/api/ask", json={"question": question})
    assert response.status_code == 200
    assert response.json()["success"] is False
    assert _row_count(settings.db_path) == before
    assert client.get("/api/summary").json()["total_revenue"] == 1150.0


def test_database_error_does_not_leak_internals(client, monkeypatch):
    def boom(*_args, **_kwargs):
        raise DatabaseError("no such table: secret_internal_table at /srv/private/path.db")

    monkeypatch.setattr(analytics, "total_revenue", boom)
    response = client.get("/api/summary")
    assert response.status_code == 503
    text = response.text
    assert "secret_internal_table" not in text and "Traceback" not in text
    assert response.json()["success"] is False


def test_unexpected_error_returns_generic_500(client, monkeypatch):
    monkeypatch.setattr(analytics, "monthly_revenue", lambda *_: 1 / 0)
    response = client.get("/api/analytics/monthly")
    assert response.status_code == 500
    assert "ZeroDivisionError" not in response.text


def test_analytics_endpoints(client):
    monthly = client.get("/api/analytics/monthly").json()["items"]
    assert [m["month"] for m in monthly] == ["2026-01", "2026-02", "2026-03"]
    products = client.get("/api/analytics/products").json()["items"]
    assert products[0]["label"] == "A"
    regions = client.get("/api/analytics/regions").json()["items"]
    assert regions[0]["label"] == "South"


def test_transactions_pagination_and_validation(client):
    page = client.get("/api/transactions", params={"page": 1, "page_size": 3}).json()
    assert page["total"] == 7 and len(page["items"]) == 3
    t6 = client.get("/api/transactions", params={"product": "C", "page_size": 10}).json()["items"]
    missing = next(i for i in t6 if i["transaction_id"] == "T6")
    assert missing["unit_price"] is None and missing["net_revenue"] is None
    assert client.get("/api/transactions", params={"page": 0}).status_code == 422
    assert client.get("/api/transactions", params={"page_size": 1000}).status_code == 422


def test_data_quality_endpoint(client):
    body = client.get("/api/data-quality").json()
    assert body["import"]["duplicate_rows"] == 1
    assert body["issues"] == {"returned": 1, "missing_unit_price": 1, "zero_quantity": 1,
                              "unknown_status": 0, "discount_exceeds_gross": 0}
    assert len(body["rejected_records"]) == 4
