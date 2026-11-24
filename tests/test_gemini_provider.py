"""Unit tests for GeminiGenAIProvider and GenAIAnalyzer retry/fail-fast logic."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from backend.config import settings
from backend.schemas.call_analysis import CallAnalysisResult
from backend.services.genai.analyzer import GenAIAnalyzer
from backend.services.genai.gemini_genai import GeminiGenAIProvider
from backend.services.genai.interface import (
    AnalysisError,
    GenAIProvider,
    NonRetryableAnalysisError,
)


def _valid_llm_json(call_id: str = "WRONG-ID") -> str:
    return json.dumps({
        "call_id": call_id,
        "analyzed_at": "2020-01-01T00:00:00Z",
        "transcript_language": "ar",
        "speakers": [{"speaker": "customer", "text": "الفلوس اتسحبت مرتين", "turn_index": 0}],
        "sentiment": {
            "overall": "negative",
            "score": 3.0,
            "trajectory": "stable",
            "evidence": ["الفلوس اتسحبت مرتين"],
        },
        "problem": {
            "summary": "Customer was charged twice.",
            "category": "billing",
            "priority": "high",
            "priority_rationale": "Duplicate payment error.",
            "keywords": ["اتسحبت مرتين"],
        },
        "agent_evaluation": {
            "empathy_score": 8.0,
            "clarity_score": 8.0,
            "resolution_effectiveness_score": 7.0,
            "professionalism_score": 9.0,
            "overall_score": 8.0,
            "strengths": ["Polite"],
            "areas_for_improvement": ["Faster SLA"],
            "evaluation_evidence": ["أعتذر لحضرتك"],
        },
        "resolution": {
            "resolved": False,
            "resolution_type": "pending_follow_up",
            "resolution_summary": "Refund initiated.",
            "follow_up_required": True,
            "follow_up_actions": ["Send confirmation SMS"],
        },
        "call_summary": "Customer reported a duplicate charge and agent initiated a refund.",
        "key_insights": ["Duplicate charge detected."],
        "recommendations": ["Add payment idempotency."],
        "confidence_score": 0.9,
        "low_confidence_flags": [],
    })


def test_gemini_missing_key_raises_non_retryable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "gemini_api_key", "")
    with pytest.raises(NonRetryableAnalysisError, match="GEMINI_API_KEY"):
        GeminiGenAIProvider()


@pytest.mark.asyncio
async def test_gemini_parses_and_enforces_server_call_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "gemini_api_key", "fake-test-key")
    provider = GeminiGenAIProvider(model="gemini-3.5-flash")
    monkeypatch.setattr(provider, "_call_generate", lambda s, u: f"```json\n{_valid_llm_json('HALLUCINATED')}\n```")

    res = await provider.analyze_transcript("الفلوس اتسحبت مرتين", call_id="SERVER-123", language="ar")
    assert res.call_id == "SERVER-123"
    assert res.raw_transcript == "الفلوس اتسحبت مرتين"
    assert res.analysis_meta is not None
    assert res.analysis_meta["provider"] == "gemini"
    assert res.analysis_meta["model"] == "gemini-3.5-flash"


@pytest.mark.asyncio
async def test_gemini_retries_once_on_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "gemini_api_key", "fake-test-key")
    provider = GeminiGenAIProvider(model="gemini-3.5-flash")
    calls = {"count": 0}

    def fake_gen(s: str, u: str) -> str:
        calls["count"] += 1
        if calls["count"] == 1:
            return "{not valid json"
        return _valid_llm_json("CALL-RETRY")

    monkeypatch.setattr(provider, "_call_generate", fake_gen)
    res = await provider.analyze_transcript("الفلوس اتسحبت مرتين", call_id="CALL-RETRY", language="ar")
    assert calls["count"] == 2
    assert res.call_id == "CALL-RETRY"


@pytest.mark.asyncio
async def test_analyzer_retries_transient_but_stops_on_non_retryable() -> None:
    class FlakyProvider(GenAIProvider):
        def __init__(self) -> None:
            self.attempts = 0

        async def analyze_transcript(self, transcript: str, call_id: str, language: str = "ar") -> CallAnalysisResult:
            self.attempts += 1
            if self.attempts < 2:
                raise AnalysisError("transient 503")
            return CallAnalysisResult.model_validate_json(_valid_llm_json(call_id))

    flaky = FlakyProvider()
    analyzer = GenAIAnalyzer(flaky, max_retries=2)
    res = await analyzer.analyze("test transcript text", "CALL-FLAKY")
    assert flaky.attempts == 2
    assert res.call_id == "CALL-FLAKY"

    class AuthFailProvider(GenAIProvider):
        def __init__(self) -> None:
            self.attempts = 0

        async def analyze_transcript(self, transcript: str, call_id: str, language: str = "ar") -> CallAnalysisResult:
            self.attempts += 1
            raise NonRetryableAnalysisError("bad api key")

    auth_fail = AuthFailProvider()
    analyzer2 = GenAIAnalyzer(auth_fail, max_retries=3)
    with pytest.raises(NonRetryableAnalysisError):
        await analyzer2.analyze("test transcript text", "CALL-AUTH")
    assert auth_fail.attempts == 1
