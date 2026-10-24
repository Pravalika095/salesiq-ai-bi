"""FastAPI application: routes, startup data load and error handling.

Run with:  uvicorn app.main:app --reload --port 8000   (from the backend folder)
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import analytics
from .ai_interpreter import LLMClient, build_llm_client
from .config import Settings, load_settings
from .data_loader import CSVValidationError, import_csv
from .database import DatabaseError, check_connection, read_connection
from .schemas import AskRequest, AskResponse, HealthResponse
from .services import answer_question, build_summary

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("salesiq.api")

_UNSET: Any = object()


def create_app(settings: Settings | None = None, llm_client: LLMClient | None = _UNSET) -> FastAPI:
    settings = settings or load_settings()
    client = build_llm_client(settings) if llm_client is _UNSET else llm_client

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Create the schema and import the CSV if needed (idempotent: unchanged CSV is skipped).
        try:
            summary = import_csv(settings.csv_path, settings.db_path)
            logger.info("Data ready: %s rows stored, %s rejected (skipped=%s)",
                        summary["imported_rows"], summary["rejected_rows"], summary["skipped"])
        except (CSVValidationError, DatabaseError, OSError) as exc:
            # Keep serving: /api/health reports the degraded state.
            logger.error("Startup data import failed: %s", exc)
        mode = f"LLM ({client.provider}/{client.model})" if client else "deterministic fallback parser"
        logger.info("Question interpretation mode: %s", mode)
        yield

    app = FastAPI(title="SalesIQ API", version="1.0.0", lifespan=lifespan,
                  description="Mini AI Business Intelligence Assistant over the supplied sales CSV.")
    app.state.settings = settings
    app.state.llm_client = client

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    # ---------------- Error handling: never leak stack traces ---------------- #

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        messages = []
        for err in exc.errors():
            field = ".".join(str(p) for p in err.get("loc", []) if p not in ("body", "query"))
            messages.append(f"{field}: {err.get('msg', 'invalid value')}".replace("Value error, ", ""))
        return JSONResponse(status_code=422, content={"success": False, "error": "Invalid request",
                                                      "details": messages})

    @app.exception_handler(DatabaseError)
    async def _db_error(_: Request, exc: DatabaseError) -> JSONResponse:
        logger.error("Database error: %s", exc)
        return JSONResponse(status_code=503, content={
            "success": False, "error": "The sales database is currently unavailable. Please try again later."})

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error")
        return JSONResponse(status_code=500, content={
            "success": False, "error": "An unexpected error occurred. Please try again."})

    # ------------------------------- Routes --------------------------------- #

    @app.get("/api/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        connected, loaded = check_connection(settings.db_path)
        return HealthResponse(
            status="ok" if connected and loaded else "degraded",
            database_connected=connected,
            data_loaded=loaded,
            ai_mode="llm" if client else "fallback",
            ai_provider=client.provider if client else None,
            ai_model=client.model if client else None,
        )

    @app.get("/api/summary")
    def summary() -> dict[str, Any]:
        return build_summary(settings.db_path)

    @app.post("/api/ask", response_model=AskResponse)
    def ask(request: AskRequest) -> AskResponse:
        return answer_question(request.question, settings.db_path, client)

    @app.get("/api/analytics/monthly")
    def monthly() -> dict[str, Any]:
        with read_connection(settings.db_path) as conn:
            return {"currency": "INR", "items": analytics.monthly_revenue(conn)}

    def _breakdown(dimension: str) -> dict[str, Any]:
        with read_connection(settings.db_path) as conn:
            return {"currency": "INR", "dimension": dimension, "items": analytics.revenue_by(conn, dimension)}

    @app.get("/api/analytics/products")
    def products() -> dict[str, Any]:
        return _breakdown("product")

    @app.get("/api/analytics/regions")
    def regions() -> dict[str, Any]:
        return _breakdown("region")

    @app.get("/api/analytics/categories")
    def categories() -> dict[str, Any]:
        return _breakdown("category")

    @app.get("/api/analytics/channels")
    def channels() -> dict[str, Any]:
        return _breakdown("channel")

    @app.get("/api/data-quality")
    def data_quality() -> dict[str, Any]:
        with read_connection(settings.db_path) as conn:
            return analytics.data_quality(conn)

    @app.get("/api/transactions")
    def transactions(
        page: int = Query(1, ge=1, le=10_000),
        page_size: int = Query(20, ge=1, le=100),
        product: str | None = Query(None, max_length=60),
        region: str | None = Query(None, max_length=60),
        category: str | None = Query(None, max_length=60),
        channel: str | None = Query(None, max_length=60),
        status: str | None = Query(None, max_length=30),
    ) -> dict[str, Any]:
        filters = {"product": product, "region": region, "category": category,
                   "channel": channel, "status": status}
        with read_connection(settings.db_path) as conn:
            return analytics.list_transactions(conn, page, page_size, filters)

    @app.get("/api/transactions/filters")
    def transaction_filters() -> dict[str, Any]:
        with read_connection(settings.db_path) as conn:
            return analytics.filter_options(conn)

    return app


app = create_app()
