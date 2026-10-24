"""Application configuration.

All settings come from environment variables (optionally loaded from a `.env`
file in the project root or the backend folder). Relative paths are resolved
against the backend directory, so the app does not depend on the current
working directory.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent

# Project-root .env first, then backend/.env; real environment variables win.
load_dotenv(PROJECT_ROOT / ".env", override=False)
load_dotenv(BACKEND_DIR / ".env", override=False)

logger = logging.getLogger("salesiq.config")

SUPPORTED_PROVIDERS = {"none", "openai", "gemini"}
DEFAULT_MODELS = {"openai": "gpt-4o-mini", "gemini": "gemini-2.5-flash"}


def _resolve_path(value: str | None, default: Path) -> Path:
    if not value:
        return default
    path = Path(value)
    return path if path.is_absolute() else (BACKEND_DIR / path).resolve()


@dataclass(frozen=True)
class Settings:
    db_path: Path
    csv_path: Path
    llm_provider: str = "none"
    llm_api_key: str | None = field(default=None, repr=False)
    llm_model: str | None = None
    llm_base_url: str | None = None
    llm_timeout_seconds: float = 15.0
    cors_origins: tuple[str, ...] = ("http://localhost:5173", "http://127.0.0.1:5173")

    @property
    def llm_enabled(self) -> bool:
        return self.llm_provider != "none" and bool(self.llm_api_key)


def load_settings() -> Settings:
    provider = (os.getenv("LLM_PROVIDER") or "none").strip().lower()
    if provider not in SUPPORTED_PROVIDERS:
        logger.warning("Unknown LLM_PROVIDER %r; using deterministic fallback parser.", provider)
        provider = "none"

    api_key = (os.getenv("LLM_API_KEY") or "").strip() or None
    if provider != "none" and not api_key:
        logger.warning("LLM_PROVIDER=%s but LLM_API_KEY is empty; using fallback parser.", provider)

    model = (os.getenv("LLM_MODEL") or "").strip() or DEFAULT_MODELS.get(provider)

    try:
        timeout = float(os.getenv("LLM_TIMEOUT_SECONDS", "15"))
    except ValueError:
        logger.warning("Invalid LLM_TIMEOUT_SECONDS; using 15 seconds.")
        timeout = 15.0

    origins = tuple(
        o.strip()
        for o in (os.getenv("CORS_ORIGINS") or "http://localhost:5173,http://127.0.0.1:5173").split(",")
        if o.strip()
    )

    return Settings(
        db_path=_resolve_path(os.getenv("DATABASE_PATH"), BACKEND_DIR / "data" / "salesiq.db"),
        csv_path=_resolve_path(os.getenv("CSV_PATH"), BACKEND_DIR / "data" / "sales_data.csv"),
        llm_provider=provider,
        llm_api_key=api_key,
        llm_model=model,
        llm_base_url=(os.getenv("LLM_BASE_URL") or "").strip() or None,
        llm_timeout_seconds=timeout,
        cors_origins=origins,
    )
