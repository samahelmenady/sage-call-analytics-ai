"""Unit tests for config precedence and transcription octet-stream MIME fallback."""

from __future__ import annotations

import io

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.config import Settings
from backend.routers.transcription import make_transcription_router
from backend.services.stt.interface import STTProvider


class _StubSTT(STTProvider):
    async def transcribe(self, audio_bytes: bytes, mime_type: str) -> str:
        return f"ok:{mime_type}"


def test_octet_stream_infers_mime_from_extension() -> None:
    app = FastAPI()
    app.include_router(make_transcription_router(_StubSTT()), prefix="/api")
    client = TestClient(app)

    resp = client.post(
        "/api/transcribe",
        files={"file": ("call.m4a", io.BytesIO(b"fake-m4a-data"), "application/octet-stream")},
    )
    assert resp.status_code == 200
    assert resp.json()["transcript"] == "ok:audio/m4a"


def test_settings_defaults_without_env_file() -> None:
    s = Settings(_env_file=None)
    assert s.genai_provider == "auto"
    assert s.gemini_model == "gemini-3.5-flash"
    assert s.stt_provider == "cohere"
