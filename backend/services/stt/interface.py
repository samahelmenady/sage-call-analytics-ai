"""
Provider-independent speech-to-text interface.

Any STT backend must subclass STTProvider and implement transcribe().
The router only depends on this interface — switching providers requires no
changes to the router or any other module.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class STTError(Exception):
    """Raised when the STT provider returns an error or is unavailable."""


class STTProvider(ABC):
    @abstractmethod
    async def transcribe(self, audio_bytes: bytes, mime_type: str) -> str:
        """
        Transcribe audio bytes to text.

        Parameters
        ----------
        audio_bytes : bytes
            Raw audio file content.
        mime_type : str
            MIME type of the audio (e.g. "audio/wav", "audio/mpeg").
            Implementations may use this to pick a file extension for the
            provider's upload API.

        Returns
        -------
        str
            Transcribed text.

        Raises
        ------
        STTError
            If the provider returns an error or the network call fails.
        """
