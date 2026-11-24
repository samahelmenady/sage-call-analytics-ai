"""
Application settings loaded from environment variables / .env file.

All fields have safe defaults so the app starts without a .env file
(STT and GenAI calls will fail cleanly with 503/502 without API keys).
"""

from __future__ import annotations

import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_CALLS_DIR = (
    Path("/tmp/sage_calls") if os.getenv("VERCEL") else (_PROJECT_ROOT / "data" / "calls")
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # STT / Cohere
    cohere_api_key: str = ""
    stt_provider: str = "cohere"
    stt_model: str = "cohere-transcribe-arabic-07-2026"
    stt_language: str = "ar"

    # GenAI ("auto" | "gemini" | "cohere")
    genai_provider: str = "auto"
    genai_model: str = ""
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash"
    cohere_genai_model: str = "command-r-plus-08-2024"
    genai_api_key: str = ""
    openai_api_key: str = ""

    # Analysis
    default_language: str = "ar"
    max_transcript_chars: int = 50_000
    analysis_timeout_seconds: int = 60

    # Server
    backend_port: int = 8000
    cors_origins: str = (
        "http://localhost:5500,http://127.0.0.1:5500,"
        "http://localhost:8000,http://127.0.0.1:8000"
    )

    # Storage & paths
    calls_dir: Path = _DEFAULT_CALLS_DIR

    @property
    def project_root(self) -> Path:
        return _PROJECT_ROOT

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
