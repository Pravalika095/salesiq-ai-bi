"""Question interpretation: deterministic fallback and (mocked) LLM path."""

from __future__ import annotations

import json

import pytest

from app.ai_interpreter import LLMError, fallback_interpret, interpret
from app.schemas import IntentName

MONTHS = ["2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06"]


@pytest.mark.parametrize("question,intent", [
    ("What is the total revenue?", "total_revenue"),
    ("What is our total revenue?", "total_revenue"),
    ("How much revenue did we generate?", "total_revenue"),
    ("Which product generated the highest revenue?", "top_product"),
    ("Which product has the highest sales revenue?", "top_product"),
    ("What is the monthly revenue trend?", "monthly_revenue"),
    ("Show me the monthly sales trend.", "monthly_revenue"),
    ("Which region generated the highest sales?", "top_region"),
    ("Which region performs best?", "top_region"),
    ("Show me sales by product.", "product_breakdown"),
    ("Show revenue by region.", "region_breakdown"),
    ("Which products generated the least revenue?", "bottom_product"),
    ("Revenue by category", "category_breakdown"),
    ("Online vs retail sales", "channel_breakdown"),
    ("How many units did we sell?", "total_units"),
])
def test_fallback_recognises_supported_phrasings(question, intent):
    result, _ = fallback_interpret(question, MONTHS)
    assert result.intent.value == intent


def test_fallback_extracts_two_months_with_shared_year():
    result, _ = fallback_interpret("Compare January and February 2026.", MONTHS)
    assert result.intent == IntentName.compare_months
    assert (result.parameters.first_month, result.parameters.second_month) == ("2026-01", "2026-02")


def test_fallback_infers_year_from_data_and_says_so():
    result, notes = fallback_interpret("What was the revenue growth between March and April?", MONTHS)
    assert (result.parameters.first_month, result.parameters.second_month) == ("2026-03", "2026-04")
    assert any("assumed 2026" in n for n in notes)


def test_fallback_asks_for_year_when_month_is_ambiguous():
    result, _ = fallback_interpret("Compare March and April", ["2025-03", "2025-04", "2026-03", "2026-04"])
    assert result.intent == IntentName.unsupported
    assert "year" in result.clarification


def test_fallback_asks_for_months_when_none_given():
    result, _ = fallback_interpret("How did revenue change between two months?", MONTHS)
    assert result.intent == IntentName.unsupported
    assert "two months" in result.clarification


@pytest.mark.parametrize("question", ["What is our profit?", "Who won the world cup?", "hello",
                                      "Forecast next month's revenue"])
def test_fallback_rejects_unsupported_questions(question):
    result, _ = fallback_interpret(question, MONTHS)
    assert result.intent == IntentName.unsupported


def test_may_as_verb_is_not_a_month():
    result, _ = fallback_interpret("May I know the total revenue?", MONTHS)
    assert result.intent == IntentName.total_revenue
    assert result.parameters.month is None


class FakeLLM:
    provider = "fake"
    model = "fake-model"

    def __init__(self, reply=None, error=None):
        self.reply, self.error, self.calls = reply, error, 0

    def complete_json(self, system_prompt, user_prompt):
        self.calls += 1
        if self.error:
            raise self.error
        return self.reply


def test_interpret_without_llm_uses_fallback_mode():
    result = interpret("What is the total revenue?", MONTHS, None)
    assert result.mode == "fallback"
    assert result.result.intent == IntentName.total_revenue


def test_valid_llm_output_is_used_and_labelled_llm():
    llm = FakeLLM(reply=json.dumps({"intent": "compare_months",
                                    "parameters": {"first_month": "2026-04", "second_month": "2026-05"}}))
    result = interpret("How did April do compared to May?", MONTHS, llm)
    assert result.mode == "llm"
    assert result.result.parameters.first_month == "2026-04"


def test_llm_output_in_code_fence_is_accepted():
    llm = FakeLLM(reply='```json\n{"intent": "top_region", "parameters": {}}\n```')
    assert interpret("best region?", MONTHS, llm).result.intent == IntentName.top_region


@pytest.mark.parametrize("reply", [
    "not json at all",
    json.dumps({"intent": "drop_table"}),
    json.dumps({"intent": "total_revenue", "parameters": {"month": "March"}}),
    json.dumps({"intent": "compare_months", "parameters": {"first_month": "2026-01"}}),
    json.dumps({"intent": "total_revenue", "parameters": {"sql": "DELETE FROM sales_transactions"}}),
])
def test_invalid_llm_output_falls_back_safely(reply):
    result = interpret("What is the total revenue?", MONTHS, FakeLLM(reply=reply))
    assert result.mode == "fallback_after_llm_error"
    assert result.result.intent == IntentName.total_revenue


def test_llm_network_failure_falls_back():
    result = interpret("Which region performs best?", MONTHS, FakeLLM(error=LLMError("timeout")))
    assert result.mode == "fallback_after_llm_error"
    assert result.result.intent == IntentName.top_region
    assert any("rule-based parser" in n for n in result.notes)
