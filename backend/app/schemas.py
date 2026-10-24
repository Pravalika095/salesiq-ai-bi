"""Pydantic request/response models and the structured intent schema."""

from __future__ import annotations

import re
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_QUESTION_LENGTH = 500
_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


class IntentName(str, Enum):
    total_revenue = "total_revenue"
    top_product = "top_product"
    bottom_product = "bottom_product"
    monthly_revenue = "monthly_revenue"
    top_region = "top_region"
    bottom_region = "bottom_region"
    compare_months = "compare_months"
    product_breakdown = "product_breakdown"
    region_breakdown = "region_breakdown"
    category_breakdown = "category_breakdown"
    channel_breakdown = "channel_breakdown"
    total_units = "total_units"
    unsupported = "unsupported"


# Intents that accept an optional single-month filter.
MONTH_FILTERABLE = {
    IntentName.total_revenue, IntentName.total_units,
    IntentName.top_product, IntentName.bottom_product,
    IntentName.top_region, IntentName.bottom_region,
    IntentName.product_breakdown, IntentName.region_breakdown,
    IntentName.category_breakdown, IntentName.channel_breakdown,
}


class IntentParameters(BaseModel):
    """Parameters an intent may carry. Every value is validated as YYYY-MM."""

    model_config = ConfigDict(extra="forbid")

    month: str | None = None
    first_month: str | None = None
    second_month: str | None = None

    @field_validator("month", "first_month", "second_month")
    @classmethod
    def _valid_month(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not _MONTH_RE.match(value):
            raise ValueError("month must use the format YYYY-MM")
        return value


class InterpretedQuestion(BaseModel):
    """The structured output of the interpreter (LLM or fallback)."""

    model_config = ConfigDict(extra="ignore")

    intent: IntentName
    parameters: IntentParameters = Field(default_factory=IntentParameters)
    clarification: str | None = None


class AskRequest(BaseModel):
    question: str = Field(..., max_length=MAX_QUESTION_LENGTH)

    @field_validator("question")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("question must not be empty")
        return value


class ChartSpec(BaseModel):
    type: Literal["bar", "line"]
    x_key: str
    y_key: str
    title: str


class AskMetadata(BaseModel):
    source: str = "sqlite"
    ai_mode: Literal["llm", "fallback", "fallback_after_llm_error"]
    ai_provider: str | None = None
    ai_model: str | None = None
    filters: dict[str, Any] = Field(default_factory=dict)
    row_count: int = 0
    notes: list[str] = Field(default_factory=list)


class AskResponse(BaseModel):
    success: bool
    question: str
    intent: str
    answer: str
    unit: str | None = "INR"
    value: float | int | None = None
    supporting_data: list[dict[str, Any]] = Field(default_factory=list)
    chart: ChartSpec | None = None
    metadata: AskMetadata


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    database_connected: bool
    data_loaded: bool
    ai_mode: Literal["llm", "fallback"]
    ai_provider: str | None
    ai_model: str | None


class ErrorResponse(BaseModel):
    success: bool = False
    error: str
