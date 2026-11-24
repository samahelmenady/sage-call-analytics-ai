"""Unit tests for JsonCallRepository."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.schemas.call_analysis import CallAnalysisResult
from backend.services.call_repository import JsonCallRepository


def _sample_result(call_id: str = "CALL-1", sentiment: str = "positive", category: str = "billing", resolved: bool = True) -> CallAnalysisResult:
    return CallAnalysisResult.model_validate({
        "call_id": call_id,
        "analyzed_at": "2026-11-24T20:00:00Z",
        "transcript_language": "en",
        "speakers": [],
        "sentiment": {"overall": sentiment, "score": 8.0, "trajectory": "stable", "evidence": ["thanks"]},
        "problem": {"summary": "Billing question", "category": category, "priority": "low", "priority_rationale": "Simple", "keywords": ["bill"]},
        "agent_evaluation": {
            "empathy_score": 8.0, "clarity_score": 8.0,
            "resolution_effectiveness_score": 8.0, "professionalism_score": 9.0,
            "overall_score": 8.2, "strengths": ["Clear"], "areas_for_improvement": [],
            "evaluation_evidence": ["happy to help"],
        },
        "resolution": {"resolved": resolved, "resolution_type": "fully_resolved", "resolution_summary": "Done", "follow_up_required": False, "follow_up_actions": []},
        "call_summary": "Customer asked about billing and agent resolved it.",
        "key_insights": ["Quick resolution"],
        "recommendations": ["None"],
        "confidence_score": 0.95,
        "low_confidence_flags": [],
    })


@pytest.mark.asyncio
async def test_save_get_list_delete(tmp_path: Path) -> None:
    repo = JsonCallRepository(tmp_path)
    r1 = _sample_result("CALL-1", "positive", "billing", True)
    r2 = _sample_result("CALL-2", "negative", "technical", False)

    await repo.save(r1)
    await repo.save(r2)

    loaded = await repo.get("CALL-1")
    assert loaded is not None
    assert loaded.call_id == "CALL-1"

    all_calls = await repo.list_all()
    assert len(all_calls) == 2

    neg_calls = await repo.list_all(filters={"sentiment": "negative"})
    assert len(neg_calls) == 1
    assert neg_calls[0].call_id == "CALL-2"

    assert await repo.delete("CALL-1") is True
    assert await repo.get("CALL-1") is None
    assert await repo.delete("CALL-1") is False
