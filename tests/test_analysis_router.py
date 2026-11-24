"""API-level tests for POST /api/analyze, GET /api/calls, and GET /api/analytics."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.routers.analysis import make_analysis_router
from backend.routers.analytics import make_analytics_router
from backend.routers.calls import make_calls_router
from backend.schemas.call_analysis import CallAnalysisResult
from backend.services.call_repository import JsonCallRepository
from backend.services.genai.analyzer import GenAIAnalyzer
from backend.services.genai.interface import AnalysisError, GenAIProvider


class StubGenAIProvider(GenAIProvider):
    def __init__(self, should_fail: bool = False) -> None:
        self._should_fail = should_fail

    async def analyze_transcript(self, transcript: str, call_id: str, language: str = "ar") -> CallAnalysisResult:
        if self._should_fail:
            raise AnalysisError("Simulated provider failure")
        return CallAnalysisResult.model_validate({
            "call_id": call_id,
            "analyzed_at": "2026-11-24T20:00:00Z",
            "transcript_language": "en",
            "speakers": [{"speaker": "customer", "text": transcript, "turn_index": 0}],
            "sentiment": {"overall": "positive", "score": 8.5, "trajectory": "stable", "evidence": ["great"]},
            "problem": {"summary": "Order inquiry", "category": "shipping", "priority": "low", "priority_rationale": "Routine", "keywords": ["order"]},
            "agent_evaluation": {
                "empathy_score": 8.0, "clarity_score": 8.5,
                "resolution_effectiveness_score": 9.0, "professionalism_score": 9.0,
                "overall_score": 8.6, "strengths": ["Fast"], "areas_for_improvement": [],
                "evaluation_evidence": ["resolved"],
            },
            "resolution": {"resolved": True, "resolution_type": "fully_resolved", "resolution_summary": "Tracked", "follow_up_required": False, "follow_up_actions": []},
            "call_summary": "Customer asked about order status and agent provided tracking.",
            "key_insights": ["Fast tracking lookup"],
            "recommendations": ["Send proactive SMS"],
            "confidence_score": 0.92,
            "low_confidence_flags": [],
        })


@pytest.fixture
def client(tmp_path: Path):
    repo = JsonCallRepository(tmp_path)
    analyzer = GenAIAnalyzer(StubGenAIProvider(), max_retries=0)
    app = FastAPI()
    app.include_router(make_analysis_router(analyzer, repo), prefix="/api")
    app.include_router(make_calls_router(repo), prefix="/api")
    app.include_router(make_analytics_router(repo), prefix="/api")
    return TestClient(app)


def test_analyze_empty_returns_400(client: TestClient) -> None:
    resp = client.post("/api/analyze", json={"transcript": "   "})
    assert resp.status_code == 400


def test_analyze_too_short_returns_400(client: TestClient) -> None:
    resp = client.post("/api/analyze", json={"transcript": "hello world"})
    assert resp.status_code == 400


def test_analyze_happy_path_and_persistence(client: TestClient) -> None:
    long_tx = "Customer called to ask about their order shipping status and agent helped them."
    resp = client.post("/api/analyze", json={"transcript": long_tx, "language": "en"})
    assert resp.status_code == 200
    body = resp.json()
    call_id = body["call_id"]
    assert body["problem"]["category"] == "shipping"

    # Verify persisted in /api/calls
    list_resp = client.get("/api/calls")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    get_resp = client.get(f"/api/calls/{call_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["call_id"] == call_id

    # Verify /api/analytics
    ana_resp = client.get("/api/analytics")
    assert ana_resp.status_code == 200
    ana = ana_resp.json()
    assert ana["total_calls"] == 1
    assert ana["resolution_rate"] == 1.0

    # Delete
    del_resp = client.delete(f"/api/calls/{call_id}")
    assert del_resp.status_code == 200
    assert client.get(f"/api/calls/{call_id}").status_code == 404


def test_analyze_provider_error_returns_502(tmp_path: Path) -> None:
    repo = JsonCallRepository(tmp_path)
    analyzer = GenAIAnalyzer(StubGenAIProvider(should_fail=True), max_retries=0)
    app = FastAPI()
    app.include_router(make_analysis_router(analyzer, repo), prefix="/api")
    c = TestClient(app)

    long_tx = "Customer called to ask about their order shipping status and agent helped them."
    resp = c.post("/api/analyze", json={"transcript": long_tx})
    assert resp.status_code == 502
