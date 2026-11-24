"""
Google Gemini GenAI provider for customer support call analysis.

Uses the official `google-genai` SDK with native JSON structured outputs,
PII/prompt-injection sanitization, deterministic grounding/consistency checks,
and rule-based customer risk scoring.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from datetime import datetime, timezone
from typing import Optional

from pydantic import ValidationError

from backend.config import settings
from backend.schemas.call_analysis import CallAnalysisResult, LLMCallAnalysisSchema
from backend.services.genai.interface import (
    AnalysisError,
    GenAIProvider,
    NonRetryableAnalysisError,
)
from backend.services.genai.postprocessor import validate_and_enrich_result
from backend.services.genai.prompts.prompt_builder import build_analysis_prompt
from backend.services.security import sanitize_error_message, sanitize_transcript_for_llm

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", flags=re.IGNORECASE)


def _strip_fences(text: str) -> str:
    return _FENCE_RE.sub("", text.strip()).strip()


def _is_non_retryable(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(
        token in msg
        for token in (
            "api_key_invalid",
            "api key not valid",
            "permission_denied",
            "unauthorized",
            "401",
            "403",
            "404",
            "invalid argument",
            "not found",
            "not_found",
        )
    )


class GeminiGenAIProvider(GenAIProvider):
    """GenAI provider backed by Google Gemini (google-genai SDK)."""

    provider_name = "gemini"

    def __init__(
        self,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        timeout_seconds: Optional[int] = None,
        rubric: Optional[dict] = None,
    ) -> None:
        api_key = settings.gemini_api_key
        if not api_key:
            raise NonRetryableAnalysisError(
                "GEMINI_API_KEY is not set. Add it to your .env file to use Gemini."
            )
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise NonRetryableAnalysisError(
                "The 'google-genai' package is not installed. Run: pip install google-genai"
            ) from exc

        self._genai = genai
        self._types = types
        self._model = model or settings.gemini_model
        self.model_name = self._model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._timeout = timeout_seconds or settings.analysis_timeout_seconds
        self._rubric = rubric
        self._client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=self._timeout * 1000),
        )

    def _call_generate(self, system_prompt: str, user_prompt: str) -> str:
        config = self._types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=self._temperature,
            max_output_tokens=self._max_tokens,
            response_mime_type="application/json",
            response_schema=LLMCallAnalysisSchema,
        )
        response = self._client.models.generate_content(
            model=self._model,
            contents=user_prompt,
            config=config,
        )
        text = getattr(response, "text", None)
        if not text:
            raise AnalysisError("Gemini returned an empty response.")
        return text

    async def analyze_transcript(
        self,
        transcript: str,
        call_id: str,
        language: str = "ar",
    ) -> CallAnalysisResult:
        t0 = time.perf_counter()
        analyzed_at = datetime.now(timezone.utc).isoformat()
        sanitized_tx, injection_detected, redaction_flags = sanitize_transcript_for_llm(transcript)

        system_prompt, user_prompt = build_analysis_prompt(
            transcript=sanitized_tx,
            call_id=call_id,
            language=language,
            rubric=self._rubric,
            analyzed_at=analyzed_at,
        )

        try:
            raw_text = await asyncio.wait_for(
                asyncio.to_thread(self._call_generate, system_prompt, user_prompt),
                timeout=self._timeout,
            )
        except asyncio.TimeoutError as exc:
            raise AnalysisError(f"Gemini request timed out after {self._timeout}s.") from exc
        except AnalysisError:
            raise
        except Exception as exc:
            safe_msg = sanitize_error_message(str(exc))
            if _is_non_retryable(exc):
                raise NonRetryableAnalysisError(f"Gemini configuration/auth error: {safe_msg}") from exc
            raise AnalysisError(f"Gemini GenAI request failed: {safe_msg}") from exc

        def _parse_and_build(payload_text: str) -> CallAnalysisResult:
            data = json.loads(_strip_fences(payload_text))
            data["call_id"] = call_id
            data["analyzed_at"] = analyzed_at
            validated = LLMCallAnalysisSchema.model_validate(data)
            latency_ms = round((time.perf_counter() - t0) * 1000.0, 1)
            result = CallAnalysisResult(
                **validated.model_dump(),
                raw_transcript=sanitized_tx,
                analysis_meta={
                    "provider": self.provider_name,
                    "model": self._model,
                    "latency_ms": latency_ms,
                },
            )
            return validate_and_enrich_result(
                result,
                transcript=sanitized_tx,
                rubric=self._rubric,
                injection_detected=injection_detected,
                redaction_flags=redaction_flags,
            )

        try:
            return _parse_and_build(raw_text)
        except (json.JSONDecodeError, ValidationError) as first_err:
            retry_prompt = (
                f"{user_prompt}\n\n"
                f"Previous JSON failed validation:\n{first_err}\n"
                "Return ONLY corrected, valid JSON matching the exact schema."
            )
            try:
                retry_text = await asyncio.wait_for(
                    asyncio.to_thread(self._call_generate, system_prompt, retry_prompt),
                    timeout=self._timeout,
                )
                return _parse_and_build(retry_text)
            except Exception as second_err:
                raise AnalysisError(
                    f"Gemini GenAI output failed schema validation after retry: {sanitize_error_message(str(second_err))}"
                ) from second_err
