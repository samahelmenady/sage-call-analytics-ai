"""
Cohere Transcribe provider.

Uses cohere.ClientV2.audio.transcriptions.create() with the model and
language configured via environment variables (STT_MODEL, STT_LANGUAGE).
Runs blocking SDK calls off the event loop with timeout and transient retries.
"""

from __future__ import annotations

import asyncio
import os
import tempfile

from backend.config import settings
from backend.services.stt.interface import STTError, STTProvider

_MIME_TO_EXT: dict[str, str] = {
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/wave": ".wav",
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/mp4": ".mp4",
    "audio/m4a": ".m4a",
    "audio/x-m4a": ".m4a",
    "audio/ogg": ".ogg",
    "audio/flac": ".flac",
    "audio/x-flac": ".flac",
    "audio/mpeg-url": ".mpga",
    "audio/mpga": ".mpga",
    "audio/webm": ".webm",
}


class CohereSTTProvider(STTProvider):
    """STT provider backed by Cohere Transcribe (v2 API)."""

    def __init__(self, max_retries: int = 2) -> None:
        if not settings.cohere_api_key:
            raise STTError(
                "COHERE_API_KEY is not set. Add it to your .env file or environment."
            )
        try:
            import cohere  # noqa: F401
        except ImportError as exc:
            raise STTError(
                "The 'cohere' package is not installed. Run: pip install cohere"
            ) from exc

        import cohere as _cohere

        self._client = _cohere.ClientV2(api_key=settings.cohere_api_key)
        self._max_retries = max_retries

    def _transcribe_sync(self, audio_bytes: bytes, ext: str) -> str:
        tmp_path = ""
        try:
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name

            with open(tmp_path, "rb") as fh:
                response = self._client.audio.transcriptions.create(
                    model=settings.stt_model,
                    language=settings.stt_language,
                    file=fh,
                )
            return (response.text or "").strip()
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

    async def transcribe(self, audio_bytes: bytes, mime_type: str) -> str:
        ext = _MIME_TO_EXT.get(mime_type.lower(), ".wav")
        last_exc: Exception | None = None

        for attempt in range(self._max_retries + 1):
            try:
                text = await asyncio.wait_for(
                    asyncio.to_thread(self._transcribe_sync, audio_bytes, ext),
                    timeout=settings.analysis_timeout_seconds,
                )
                if not text:
                    raise STTError("Cohere STT returned an empty transcript. Check audio quality.")
                return text
            except STTError:
                raise
            except asyncio.TimeoutError as exc:
                last_exc = STTError(f"Cohere transcription timed out after {settings.analysis_timeout_seconds}s.")
                if attempt < self._max_retries:
                    await asyncio.sleep(0.5 * (2**attempt))
                    continue
                raise last_exc from exc
            except Exception as exc:
                msg = str(exc).lower()
                if any(tok in msg for tok in ("401", "403", "unauthorized", "invalid api token")):
                    raise STTError(f"Cohere STT authentication error: {exc}") from exc
                last_exc = exc
                if attempt < self._max_retries:
                    await asyncio.sleep(0.5 * (2**attempt))

        raise STTError(f"Cohere transcription failed: {last_exc}") from last_exc
