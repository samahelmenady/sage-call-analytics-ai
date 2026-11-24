"""Unit tests for GET /api/calls filters, search, sorting, and GET /api/analytics N/A exclusion."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.routers.analytics import make_analytics_router
from backend.routers.calls import make_calls_router
from backend.schemas.call_analysis import CallAnalysisResult
from backend.services.call_repository import JsonCallRepository


def _make_record(
    call_id: str,
    analyzed_at: str,
    sentiment: str,
    sat_score: float,
    category: str,
    priority: str,
    resolved: bool,
    resolution_type: str,
    empathy: float | None,
    clarity: float | None,
    res_eff: float | None,
    prof: float | None,
    overall: float | None,
    applicable: bool = True,
    sla: bool = False,
    summary: str = "Issue summary",
) -> CallAnalysisResult:
    return CallAnalysisResult.model_validate({
        "call_id": call_id,
        "analyzed_at": analyzed_at,
        "transcript_language": "ar",
        "speakers": [],
        "sentiment": {"overall": sentiment, "score": sat_score, "trajectory": "stable", "emotions": ["frustration"], "evidence": ["quote"]},
        "problem": {"summary": summary, "category": category, "priority": priority, "priority_rationale": "Reason", "keywords": ["kw"]},
        "agent_evaluation": {
            "applicable": applicable,
            "empathy_score": empathy,
            "clarity_score": clarity,
            "resolution_effectiveness_score": res_eff,
            "professionalism_score": prof,
            "overall_score": overall,
            "strengths": [],
            "areas_for_improvement": [],
            "evaluation_evidence": [],
        },
        "resolution": {
            "resolved": resolved,
            "resolution_type": resolution_type,
            "resolution_summary": "Summary",
            "follow_up_required": not resolved,
            "follow_up_actions": [],
            "escalation_required": resolution_type == "escalated",
        },
        "operational_signals": {
            "repeated_complaint": False,
            "missed_commitment": False,
            "potential_sla_violation": sla,
            "signal_evidence": [],
        },
        "call_summary": "Summary text",
        "key_insights": [],
        "recommendations": [],
        "confidence_score": 0.9,
        "low_confidence_flags": [],
    })


@pytest.fixture
async def populated_client(tmp_path: Path):
    repo = JsonCallRepository(tmp_path)
    # C1 & C2 have agent evaluations; C3 is voicemail (no agent -> N/A, must be excluded from agent averages!)
    await repo.save(_make_record("C1", "2026-11-23T10:00:00Z", "negative", 3.0, "billing", "high", False, "pending_follow_up", 7.0, 8.0, 6.0, 9.0, 7.5, True, True, "Double Visa charge"))
    await repo.save(_make_record("C2", "2026-11-24T11:00:00Z", "positive", 9.0, "technical", "medium", True, "fully_resolved", 9.0, 8.0, 10.0, 9.0, 9.0, True, False, "Router fixed"))
    await repo.save(_make_record("C3", "2026-11-24T12:00:00Z", "negative", 4.0, "billing", "critical", False, "escalated", None, None, None, None, None, False, False, "Voicemail complaint"))

    app = FastAPI()
    app.include_router(make_calls_router(repo), prefix="/api")
    app.include_router(make_analytics_router(repo), prefix="/api")
    return TestClient(app)


def test_empty_analytics(tmp_path: Path) -> None:
    repo = JsonCallRepository(tmp_path)
    app = FastAPI()
    app.include_router(make_analytics_router(repo), prefix="/api")
    c = TestClient(app)
    resp = c.get("/api/analytics")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_calls"] == 0
    assert body["evaluated_agent_calls"] == 0
    assert body["avg_agent_scores"]["overall"] is None
    assert body["daily_trends"] == []


def test_calls_filtering_search_and_analytics_excludes_na(populated_client: TestClient) -> None:
    # Filtering & search
    assert len(populated_client.get("/api/calls?category=billing").json()) == 2
    assert len(populated_client.get("/api/calls?priority=critical").json()) == 1
    assert len(populated_client.get("/api/calls?resolved=true").json()) == 1
    assert len(populated_client.get("/api/calls?search=Visa").json()) == 1
    assert len(populated_client.get("/api/calls?sla_violation=true").json()) == 1

    # Risk sorting
    by_risk = populated_client.get("/api/calls?sort_by=risk_desc").json()
    assert by_risk[0]["call_id"] in {"C1", "C3"}
    assert by_risk[-1]["call_id"] == "C2"

    # Analytics math consistency & N/A exclusion
    ana = populated_client.get("/api/analytics").json()
    assert ana["total_calls"] == 3
    assert ana["evaluated_agent_calls"] == 2  # C3 excluded!
    assert ana["avg_agent_scores"]["overall"] == round((7.5 + 9.0) / 2, 2)
    assert ana["avg_agent_scores"]["empathy"] == round((7.0 + 9.0) / 2, 2)
    assert ana["sla_violation_count"] == 1
    assert ana["escalation_count"] == 1
    assert ana["avg_satisfaction_score"] == round((3.0 + 9.0 + 4.0) / 3, 2)
    assert len(ana["daily_trends"]) == 2
    assert ana["daily_trends"][0]["date"] == "2026-11-23"
    assert ana["daily_trends"][1]["date"] == "2026-11-24"
    assert ana["daily_trends"][1]["calls"] == 2
