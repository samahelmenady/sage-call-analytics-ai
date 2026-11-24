"""
GenAI analysis orchestrator.

Wraps a primary GenAIProvider with:
  - Exact-transcript TTL/LRU caching (cuts duplicate API cost & latency)
  - Retry/backoff logic for transient failures (fails fast on NonRetryableAnalysisError)
  - Optional fallback provider on primary outage
"""

from __future__ import annotations

import asyncio
import hashlib
import re
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Optional

from backend.schemas.call_analysis import CallAnalysisResult
from backend.services.genai.interface import (
    AnalysisError,
    GenAIProvider,
    NonRetryableAnalysisError,
)


def _cache_key(transcript: str, language: str, provider: GenAIProvider) -> str:
    norm = re.sub(r"\s+", " ", transcript.strip())
    raw = f"{provider.provider_name}:{provider.model_name}:{language}:{norm}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class GenAIAnalyzer:
    """Orchestrates transcript analysis using a configured GenAIProvider."""

    def __init__(
        self,
        provider: GenAIProvider,
        max_retries: int = 1,
        fallback_provider: Optional[GenAIProvider] = None,
        cache_max_items: int = 128,
    ) -> None:
        self._provider = provider
        self._max_retries = max_retries
        self._fallback_provider = fallback_provider
        self._cache_max_items = cache_max_items
        self._cache: OrderedDict[str, CallAnalysisResult] = OrderedDict()

    @property
    def provider(self) -> GenAIProvider:
        return self._provider

    def _get_cached(self, key: str, call_id: str) -> Optional[CallAnalysisResult]:
        cached = self._cache.get(key)
        if cached is None:
            return None
        self._cache.move_to_end(key)
        copy = cached.model_copy(deep=True)
        copy.call_id = call_id
        copy.analyzed_at = datetime.now(timezone.utc).isoformat()
        meta = dict(copy.analysis_meta or {})
        meta["cache_hit"] = True
        copy.analysis_meta = meta
        return copy

    def _put_cached(self, key: str, result: CallAnalysisResult) -> None:
        if self._cache_max_items <= 0:
            return
        self._cache[key] = result.model_copy(deep=True)
        self._cache.move_to_end(key)
        while len(self._cache) > self._cache_max_items:
            self._cache.popitem(last=False)

    async def analyze(
        self,
        transcript: str,
        call_id: str,
        language: str = "ar",
        use_cache: bool = True,
    ) -> CallAnalysisResult:
        key = _cache_key(transcript, language, self._provider)
        if use_cache:
            hit = self._get_cached(key, call_id)
            if hit is not None:
                return hit

        last_exc: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                res = await self._provider.analyze_transcript(
                    transcript=transcript,
                    call_id=call_id,
                    language=language,
                )
                self._put_cached(key, res)
                return res
            except NonRetryableAnalysisError as exc:
                last_exc = exc
                break
            except AnalysisError as exc:
                last_exc = exc
                if attempt < self._max_retries:
                    await asyncio.sleep(0.5 * (2**attempt))

        if self._fallback_provider is not None:
            result = await self._fallback_provider.analyze_transcript(
                transcript=transcript,
                call_id=call_id,
                language=language,
            )
            meta = dict(result.analysis_meta or {})
            meta["fallback_from"] = f"{self._provider.provider_name}:{self._provider.model_name}"
            result.analysis_meta = meta
            self._put_cached(key, result)
            return result

        if isinstance(last_exc, NonRetryableAnalysisError):
            raise last_exc
        raise AnalysisError(
            f"Analysis failed after {self._max_retries + 1} attempts: {last_exc}"
        )
