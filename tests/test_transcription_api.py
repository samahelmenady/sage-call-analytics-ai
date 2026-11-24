"""
API-level tests for POST /api/transcribe.

All tests use StubSTTProvider — no Cohere API key is required.
The StubSTTProvider proves the interface contract and that the router
correctly validates, calls the provider, and serialises the response.

The end-to-end Cohere path is intentionally not tested here: it requires
a live API key and network access.
"""

from __future__ import annotations

import io
import os

os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.routers.transcription import make_transcription_router
from backend.services.stt.interface import STTError, STTProvider

# ---------------------------------------------------------------------------
# StubSTTProvider — always returns a fixed Arabic transcript.
# Used to test the router without any network dependency.
# ---------------------------------------------------------------------------

STUB_TRANSCRIPT = "الفندق نظيف والغرفة واسعة"


class StubSTTProvider(STTProvider):
    """Returns a fixed transcript unconditionally."""

    async def transcribe(self, audio_bytes: bytes, mime_type: str) -> str:
        return STUB_TRANSCRIPT


class FailingSTTProvider(STTProvider):
    """Always raises STTError — tests the 502 error path."""

    async def transcribe(self, audio_bytes: bytes, mime_type: str) -> str:
        raise STTError("Simulated provider failure")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_client(provider: STTProvider) -> TestClient:
    app = FastAPI()
    app.include_router(make_transcription_router(provider), prefix="/api")
    return TestClient(app)


@pytest.fixture(scope="module")
def client():
    return _make_client(StubSTTProvider())


@pytest.fixture(scope="module")
def failing_client():
    return _make_client(FailingSTTProvider())


# Minimal valid WAV header (44 bytes) — enough for MIME and size checks.
_WAV_HEADER = (
    b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00"
    b"\x01\x00\x01\x00\x44\xac\x00\x00\x88X\x01\x00"
    b"\x02\x00\x10\x00data\x00\x00\x00\x00"
)


def _wav_upload(data: bytes = _WAV_HEADER) -> dict:
    """Build the files dict for TestClient multipart upload."""
    return {"file": ("test.wav", io.BytesIO(data), "audio/wav")}


# ---------------------------------------------------------------------------
# Happy-path tests (StubSTTProvider)
# ---------------------------------------------------------------------------

def test_happy_path_returns_200(client) -> None:
    resp = client.post("/api/transcribe", files=_wav_upload())
    assert resp.status_code == 200


def test_happy_path_returns_transcript_key(client) -> None:
    resp = client.post("/api/transcribe", files=_wav_upload())
    assert "transcript" in resp.json()


def test_happy_path_transcript_value(client) -> None:
    resp = client.post("/api/transcribe", files=_wav_upload())
    assert resp.json()["transcript"] == STUB_TRANSCRIPT


def test_stub_provider_interface_contract() -> None:
    """
    StubSTTProvider must satisfy the STTProvider interface.
    This is the switching-providers test: a conforming implementation
    integrates without any change to the router.
    """
    assert isinstance(StubSTTProvider(), STTProvider)


# ---------------------------------------------------------------------------
# MIME-type validation (before provider is called)
# ---------------------------------------------------------------------------

def test_unsupported_mime_returns_400(client) -> None:
    resp = client.post(
        "/api/transcribe",
        files={"file": ("doc.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    assert resp.status_code == 400


def test_image_mime_returns_400(client) -> None:
    resp = client.post(
        "/api/transcribe",
        files={"file": ("img.png", io.BytesIO(b"\x89PNG"), "image/png")},
    )
    assert resp.status_code == 400


def test_mp3_mime_accepted(client) -> None:
    resp = client.post(
        "/api/transcribe",
        files={"file": ("audio.mp3", io.BytesIO(b"ID3\x03\x00"), "audio/mpeg")},
    )
    assert resp.status_code == 200


def test_ogg_mime_accepted(client) -> None:
    resp = client.post(
        "/api/transcribe",
        files={"file": ("audio.ogg", io.BytesIO(b"OggS"), "audio/ogg")},
    )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Size validation
# ---------------------------------------------------------------------------

def test_empty_file_returns_400(client) -> None:
    resp = client.post(
        "/api/transcribe",
        files={"file": ("empty.wav", io.BytesIO(b""), "audio/wav")},
    )
    assert resp.status_code == 400


def test_oversized_file_returns_400(client) -> None:
    big = b"\x00" * (25 * 1024 * 1024 + 1)  # 25 MB + 1 byte
    resp = client.post(
        "/api/transcribe",
        files={"file": ("big.wav", io.BytesIO(big), "audio/wav")},
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Provider error path
# ---------------------------------------------------------------------------

def test_provider_error_returns_502(failing_client) -> None:
    resp = failing_client.post("/api/transcribe", files=_wav_upload())
    assert resp.status_code == 502


def test_provider_error_body_has_detail(failing_client) -> None:
    resp = failing_client.post("/api/transcribe", files=_wav_upload())
    assert "detail" in resp.json()
