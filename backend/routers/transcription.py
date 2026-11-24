"""
POST /api/transcribe

Accepts a multipart/form-data upload with field name "file".
Transcribes the audio using the configured STT provider and returns:
  { "transcript": "<text>" }
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile
from pydantic import BaseModel

from backend.services.security import sanitize_error_message
from backend.services.stt.interface import STTError, STTProvider

_MAX_BYTES = 25 * 1024 * 1024  # 25 MB

_ALLOWED_MIME_PREFIXES = {
    "audio/wav",
    "audio/x-wav",
    "audio/wave",
    "audio/mpeg",
    "audio/mp3",
    "audio/mp4",
    "audio/m4a",
    "audio/x-m4a",
    "audio/ogg",
    "audio/flac",
    "audio/x-flac",
    "audio/mpeg-url",
    "audio/mpga",
    "audio/webm",
}

_EXT_TO_MIME = {
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
    ".mpeg": "audio/mpeg",
    ".mpga": "audio/mpga",
    ".mp4": "audio/mp4",
    ".m4a": "audio/m4a",
    ".ogg": "audio/ogg",
    ".flac": "audio/flac",
    ".webm": "audio/webm",
}


class TranscribeResponse(BaseModel):
    transcript: str


def make_transcription_router(provider: STTProvider) -> APIRouter:
    router = APIRouter()

    @router.post("/transcribe", response_model=TranscribeResponse)
    async def transcribe(file: UploadFile) -> TranscribeResponse:
        mime = (file.content_type or "").lower().split(";")[0].strip()
        if (not mime or mime == "application/octet-stream") and file.filename:
            ext = Path(file.filename).suffix.lower()
            mime = _EXT_TO_MIME.get(ext, mime)

        if mime not in _ALLOWED_MIME_PREFIXES:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Unsupported audio format '{mime}'. "
                    "Accepted: WAV, MP3, M4A, MPEG, MPGA, OGG, FLAC, WEBM."
                ),
            )

        audio_bytes = await file.read()
        if len(audio_bytes) == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")
        if len(audio_bytes) > _MAX_BYTES:
            raise HTTPException(
                status_code=400,
                detail=f"File exceeds the 25 MB limit ({len(audio_bytes):,} bytes received).",
            )

        try:
            transcript = await provider.transcribe(audio_bytes, mime)
        except STTError as exc:
            raise HTTPException(status_code=502, detail=sanitize_error_message(str(exc))) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=sanitize_error_message(str(exc))) from exc

        return TranscribeResponse(transcript=transcript)

    return router
