"""
Provider-independent Generative AI interface for call transcript analysis.

Any GenAI backend must subclass GenAIProvider and implement analyze_transcript().
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from backend.schemas.call_analysis import CallAnalysisResult


class AnalysisError(Exception):
    """Raised when the GenAI provider fails or returns invalid output."""


class NonRetryableAnalysisError(AnalysisError):
    """Raised on configuration, authentication, or invalid-request errors that should not retry."""


class GenAIProvider(ABC):
    provider_name: str = "unknown"
    model_name: str = "unknown"

    @abstractmethod
    async def analyze_transcript(
        self,
        transcript: str,
        call_id: str,
        language: str = "ar",
    ) -> CallAnalysisResult:
        """
        Analyze a call transcript and return a validated CallAnalysisResult.

        Parameters
        ----------
        transcript : str
            Full call transcript text.
        call_id : str
            Unique identifier for this call.
        language : str
            Expected transcript language ("ar", "en", or "auto").

        Returns
        -------
        CallAnalysisResult
            Validated structured analysis.

        Raises
        ------
        AnalysisError
            If the provider fails or output cannot be validated.
        """
