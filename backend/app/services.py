"""Question-answering service: interpret -> validate -> query -> answer.

The answer text is produced here from database results using fixed templates.
The LLM (if any) only chooses the intent; it never supplies the numbers.
"""

from __future__ import annotations

import logging
import re
from datetime import date
from pathlib import Path
from typing import Any

from . import analytics
from .ai_interpreter import SUPPORTED_QUESTIONS_HELP, LLMClient, interpret
from .analytics import InvalidParameterError
from .database import read_connection
from .schemas import AskMetadata, AskResponse, ChartSpec, IntentName

logger = logging.getLogger("salesiq.services")

# Questions that look like SQL / destructive commands are refused up front.
# (Even without this, nothing in the system executes SQL text from a question.)
_SQL_LIKE = re.compile(
    r";|--|/\*|\b(?:drop|alter|truncate)\s+(?:table|database|view|index)\b|\bdelete\s+from\b|"
    r"\binsert\s+into\b|\bupdate\s+\w+\s+set\b|\battach\s+database\b|\bdetach\b|\bpragma\b|"
    r"\bunion\s+(?:all\s+)?select\b|\bselect\b[\s\S]*\bfrom\b|\bsqlite_master\b",
    re.IGNORECASE,
)


def format_inr(amount: float) -> str:
    """Format rupees with Indian digit grouping: 1234567.5 -> '₹12,34,567.50'."""
    sign = "-" if amount < 0 else ""
    whole, frac = f"{abs(amount):.2f}".split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups + [tail])
    return f"{sign}₹{whole}.{frac}"


def month_label(month: str) -> str:
    return date(int(month[:4]), int(month[5:]), 1).strftime("%B %Y")


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:+.2f}%"


DIMENSION_OF = {
    IntentName.top_product: "product", IntentName.bottom_product: "product",
    IntentName.top_region: "region", IntentName.bottom_region: "region",
    IntentName.product_breakdown: "product", IntentName.region_breakdown: "region",
    IntentName.category_breakdown: "category", IntentName.channel_breakdown: "channel",
}
DIMENSION_TITLE = {"product": "Product", "region": "Region", "category": "Category", "channel": "Sales channel"}


def _answer_for_intent(conn, intent: IntentName, params) -> dict[str, Any]:
    """Run the approved analytic for an intent and build the answer payload."""
    month = params.month
    if month is not None and month not in analytics.available_months(conn):
        raise InvalidParameterError(
            f"There is no sales data for {month_label(month)}. "
            f"Available months: {', '.join(analytics.available_months(conn))}."
        )
    period = f" in {month_label(month)}" if month else ""
    filters = {"status": "Completed", "unit_price": "known"}
    if month:
        filters["month"] = month

    if intent == IntentName.total_revenue:
        t = analytics.total_revenue(conn, month)
        if t["transactions"] == 0:
            return {"answer": f"No eligible sales were found{period}.", "value": 0, "filters": filters}
        return {
            "answer": (f"Total net revenue{period} is {format_inr(t['revenue'])} from "
                       f"{t['transactions']} eligible transactions (gross {format_inr(t['gross_revenue'])} "
                       f"minus {format_inr(t['discounts'])} in discounts)."),
            "value": t["revenue"],
            "supporting_data": [
                {"metric": "Gross revenue", "value": t["gross_revenue"]},
                {"metric": "Discounts", "value": t["discounts"]},
                {"metric": "Net revenue", "value": t["revenue"]},
                {"metric": "Eligible transactions", "value": t["transactions"]},
                {"metric": "Units sold", "value": t["units"]},
            ],
            "filters": filters,
        }

    if intent == IntentName.total_units:
        t = analytics.total_revenue(conn, month)
        return {
            "answer": f"{t['units']:,} units were sold{period} across {t['transactions']} eligible transactions.",
            "value": t["units"], "unit": "units",
            "supporting_data": [
                {"metric": "Units sold", "value": t["units"]},
                {"metric": "Eligible transactions", "value": t["transactions"]},
                {"metric": "Net revenue", "value": t["revenue"]},
            ],
            "filters": filters,
        }

    if intent in (IntentName.top_product, IntentName.bottom_product,
                  IntentName.top_region, IntentName.bottom_region):
        dim = DIMENSION_OF[intent]
        lowest = intent.value.startswith("bottom")
        r = analytics.ranked(conn, dim, month, lowest=lowest)
        if r["winner"] is None:
            return {"answer": f"No eligible sales were found{period}.", "value": None, "filters": filters}
        w = r["winner"]
        word = "lowest" if lowest else "highest"
        if len(r["tied"]) > 1:
            answer = (f"{len(r['tied'])} {dim}s are tied for the {word} net revenue{period} at "
                      f"{format_inr(w['revenue'])} each: {', '.join(r['tied'])}.")
        else:
            answer = (f"{w['label']} generated the {word} net revenue{period}: {format_inr(w['revenue'])} "
                      f"({w['share_pct']:.2f}% of total) from {w['transactions']} transactions.")
        return {
            "answer": answer, "value": w["revenue"], "supporting_data": r["rows"], "filters": filters,
            "chart": ChartSpec(type="bar", x_key="label", y_key="revenue",
                               title=f"Net revenue by {dim}{period}"),
        }

    if intent in (IntentName.product_breakdown, IntentName.region_breakdown,
                  IntentName.category_breakdown, IntentName.channel_breakdown):
        dim = DIMENSION_OF[intent]
        rows = analytics.revenue_by(conn, dim, month)
        if not rows:
            return {"answer": f"No eligible sales were found{period}.", "value": None, "filters": filters}
        total = round(sum(r["revenue"] for r in rows), 2)
        top, low = rows[0], rows[-1]
        answer = (f"Net revenue by {DIMENSION_TITLE[dim].lower()}{period} across {len(rows)} groups totals "
                  f"{format_inr(total)}. {top['label']} leads with {format_inr(top['revenue'])} "
                  f"({top['share_pct']:.2f}%)")
        answer += (f"; {low['label']} is lowest with {format_inr(low['revenue'])} ({low['share_pct']:.2f}%)."
                   if len(rows) > 1 else ".")
        return {
            "answer": answer, "value": total, "supporting_data": rows, "filters": filters,
            "chart": ChartSpec(type="bar", x_key="label", y_key="revenue",
                               title=f"Net revenue by {dim}{period}"),
        }

    if intent == IntentName.monthly_revenue:
        rows = analytics.monthly_revenue(conn)
        if not rows:
            return {"answer": "No sales data is loaded.", "value": None}
        best = max(rows, key=lambda r: (r["revenue"], r["month"]))
        worst = min(rows, key=lambda r: (r["revenue"], r["month"]))
        first, last = rows[0], rows[-1]
        overall = analytics.pct_change(round(first["revenue"] * 100), round(last["revenue"] * 100))
        answer = (f"Monthly net revenue from {month_label(first['month'])} to {month_label(last['month'])}: "
                  f"highest in {month_label(best['month'])} ({format_inr(best['revenue'])}), lowest in "
                  f"{month_label(worst['month'])} ({format_inr(worst['revenue'])}). From the first to the last "
                  f"month revenue changed by {format_inr(last['revenue'] - first['revenue'])} ({_pct(overall)}).")
        return {
            "answer": answer, "value": round(sum(r["revenue"] for r in rows), 2),
            "supporting_data": rows, "filters": {"status": "Completed", "unit_price": "known"},
            "chart": ChartSpec(type="line", x_key="month", y_key="revenue", title="Monthly net revenue"),
        }

    if intent == IntentName.compare_months:
        c = analytics.compare_months(conn, params.first_month, params.second_month)
        a, b = month_label(c["first_month"]), month_label(c["second_month"])
        if c["direction"] == "unchanged":
            answer = f"Revenue was unchanged at {format_inr(c['second_revenue'])} between {a} and {b}."
        else:
            sign = "+" if c["absolute_change"] > 0 else ""
            answer = (f"Revenue {c['direction']} from {format_inr(c['first_revenue'])} in {a} to "
                      f"{format_inr(c['second_revenue'])} in {b}, a change of "
                      f"{sign}{format_inr(c['absolute_change'])}")
            if c["percent_change"] is None:
                answer += (f". The percentage change cannot be calculated because revenue in {a} "
                           f"was {format_inr(0)}.")
            else:
                answer += f" ({_pct(c['percent_change'])})."
        return {
            "answer": answer, "value": c["absolute_change"],
            "supporting_data": [
                {"month": c["first_month"], "revenue": c["first_revenue"], "transactions": c["first_transactions"]},
                {"month": c["second_month"], "revenue": c["second_revenue"], "transactions": c["second_transactions"]},
                {"month": "Change", "revenue": c["absolute_change"], "change_pct": c["percent_change"]},
            ],
            "filters": {"status": "Completed", "unit_price": "known",
                        "first_month": c["first_month"], "second_month": c["second_month"]},
            "chart": ChartSpec(type="bar", x_key="month", y_key="revenue", title=f"{a} vs {b}"),
        }

    raise InvalidParameterError(SUPPORTED_QUESTIONS_HELP)  # pragma: no cover


def answer_question(question: str, db_path: Path, llm_client: LLMClient | None) -> AskResponse:
    if _SQL_LIKE.search(question):
        return AskResponse(
            success=False, question=question, intent=IntentName.unsupported.value, unit=None,
            answer=("SQL statements and database commands are not accepted. "
                    "Please ask a business question instead. " + SUPPORTED_QUESTIONS_HELP),
            metadata=AskMetadata(ai_mode="fallback", notes=["Rejected by input guard before interpretation."]),
        )

    with read_connection(db_path) as conn:
        months = analytics.available_months(conn)
        interp = interpret(question, months, llm_client)
        meta = AskMetadata(ai_mode=interp.mode, ai_provider=interp.provider, ai_model=interp.model,
                           notes=list(interp.notes))
        result = interp.result

        if result.intent == IntentName.unsupported:
            return AskResponse(success=False, question=question, intent=result.intent.value, unit=None,
                               answer=result.clarification or SUPPORTED_QUESTIONS_HELP, metadata=meta)
        try:
            payload = _answer_for_intent(conn, result.intent, result.parameters)
        except InvalidParameterError as exc:
            return AskResponse(success=False, question=question, intent=result.intent.value,
                               unit=None, answer=str(exc), metadata=meta)

    supporting = payload.get("supporting_data", [])
    meta.filters = payload.get("filters", {})
    meta.row_count = len(supporting)
    return AskResponse(
        success=True, question=question, intent=result.intent.value, answer=payload["answer"],
        unit=payload.get("unit", "INR"), value=payload.get("value"), supporting_data=supporting,
        chart=payload.get("chart"), metadata=meta,
    )


def build_summary(db_path: Path) -> dict[str, Any]:
    with read_connection(db_path) as conn:
        totals = analytics.total_revenue(conn)
        top_product = analytics.ranked(conn, "product")
        top_region = analytics.ranked(conn, "region")
        quality = analytics.data_quality(conn)
        return {
            "total_revenue": totals["revenue"],
            "gross_revenue": totals["gross_revenue"],
            "total_discounts": totals["discounts"],
            "eligible_transactions": totals["transactions"],
            "total_units": totals["units"],
            "top_product": _winner(top_product),
            "top_region": _winner(top_region),
            "date_range": analytics.date_range(conn),
            "months": analytics.available_months(conn),
            "currency": "INR",
            "data_quality": {
                **quality["import"],
                "eligible_transactions": quality["eligible_transactions"],
                "excluded_from_revenue": quality["excluded_from_revenue"],
                "issues": quality["issues"],
            },
        }


def _winner(ranked: dict[str, Any]) -> dict[str, Any] | None:
    w = ranked["winner"]
    if w is None:
        return None
    return {"name": w["label"], "revenue": w["revenue"], "share_pct": w["share_pct"], "tied_with": ranked["tied"][1:]}
